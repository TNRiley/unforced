#!/usr/bin/env python3
"""
Unforced Error — stage 1: harvest.

Pulls the racquet-sport corner of the US iOS App Store from two public Apple
endpoints, and writes raw JSON to data/. Nothing here is interpreted; screening
and coding happen in screen.py so that stage can be re-run without re-fetching.

  1. iTunes Search API   https://itunes.apple.com/search
     One pass per query term below. Returns up to 200 records per term with
     full app metadata already attached (genre, price, ratings, description,
     release dates, seller). No key, no auth.

  2. Customer reviews RSS  https://itunes.apple.com/us/rss/customerreviews/...
     50 reviews per page, pages 1-10, so 500 reviews per app maximum, most
     recent first. This is the only free route to review *text*; the Search API
     gives counts and averages but never a single review body.

Quirks that will bite you:
  * The RSS feed's page 1 entry[0] is the APP, not a review — Apple prepends a
    summary entry. Every other page starts at entry[0] with a real review.
  * A feed with no reviews returns a body with no 'entry' key at all, not [].
  * Apple rate-limits somewhere near 20 req/s from one IP; 403s come back as
    HTML, not JSON. THROTTLE + RETRIES below are tuned to stay under it.
  * averageUserRating is the *lifetime* average over all versions; the feed's
    reviews are the most recent 500 only. They do not have to agree.
"""
import json, os, re, sys, time, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
THROTTLE = 0.12          # seconds between requests inside a worker
RETRIES = 4
REVIEW_PAGES = 10        # Apple caps the feed at 10 pages of 50

# The search strategy. Deliberately over-broad: a systematic search errs toward
# recall and lets the screening stage throw things out with a recorded reason.
# Every term is logged into the payload so the strategy is reproducible.
QUERIES = [
    "tennis", "tennis stats", "tennis scorekeeper", "tennis score", "tennis coach",
    "tennis training", "tennis drills", "tennis live scores", "tennis match",
    "tennis club", "tennis lessons", "tennis serve", "tennis video analysis",
    "tennis ladder", "tennis rankings", "utr tennis", "usta", "atp tour", "wta",
    "padel", "pickleball", "pickleball score", "squash", "racquetball", "badminton",
    "table tennis", "racket sport", "court booking",
]


def get(url, tries=RETRIES):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as r:
                raw = r.read().decode("utf-8", "replace")
            return json.loads(raw)
        except Exception as e:          # 403 HTML, timeouts, transient 5xx
            last = e
            time.sleep(1.5 * (i + 1))
    print("    ! give up %s (%s)" % (url[:90], last), file=sys.stderr)
    return None


def search():
    """One Search API call per query term. Keyed by trackId so the union dedupes."""
    apps, hits = {}, {}
    for q in QUERIES:
        url = ("https://itunes.apple.com/search?term=%s&entity=software&country=us&limit=200"
               % urllib.parse.quote(q))
        d = get(url)
        time.sleep(THROTTLE)
        if not d:
            hits[q] = 0
            continue
        res = d.get("results", [])
        hits[q] = len(res)
        for r in res:
            tid = r.get("trackId")
            if not tid:
                continue
            r.setdefault("_foundBy", [])
            if tid in apps:
                apps[tid]["_foundBy"].append(q)
            else:
                r["_foundBy"] = [q]
                apps[tid] = r
        print("  %-22s %4d results (union %d)" % (q, len(res), len(apps)))
    return apps, hits


def reviews_for(tid):
    """Up to 500 most-recent US reviews for one app."""
    out = []
    for page in range(1, REVIEW_PAGES + 1):
        url = ("https://itunes.apple.com/us/rss/customerreviews/page=%d/id=%d/"
               "sortby=mostrecent/json" % (page, tid))
        d = get(url, tries=3)
        time.sleep(THROTTLE)
        if not d:
            break
        entries = d.get("feed", {}).get("entry")
        if not entries:
            break
        if isinstance(entries, dict):     # single-entry feeds are not wrapped in a list
            entries = [entries]
        for e in entries:
            # page 1 prepends the app itself; a real review always has im:rating
            if "im:rating" not in e:
                continue
            out.append({
                "id": e.get("id", {}).get("label"),
                "app": tid,
                "rating": int(e["im:rating"]["label"]),
                "title": e.get("title", {}).get("label", ""),
                "body": e.get("content", {}).get("label", ""),
                "version": e.get("im:version", {}).get("label", ""),
                "author": e.get("author", {}).get("name", {}).get("label", ""),
                "updated": e.get("updated", {}).get("label", ""),
                "votes": int(e.get("im:voteSum", {}).get("label", 0) or 0),
            })
        if len(entries) < 50:
            break
    return out


def main():
    print("stage 1a — search (%d queries)" % len(QUERIES))
    apps, hits = search()
    print("  → %d distinct apps\n" % len(apps))
    json.dump({"apps": list(apps.values()), "queryHits": hits, "queries": QUERIES,
               "harvested": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
              open(os.path.join(DATA, "apps.json"), "w", encoding="utf-8"))

    # Only fetch reviews where there is any chance of reviews existing.
    targets = [a for a in apps.values() if (a.get("userRatingCount") or 0) >= 1]
    targets.sort(key=lambda a: -(a.get("userRatingCount") or 0))
    print("stage 1b — reviews for %d apps with >=1 US rating" % len(targets))

    all_reviews, done = [], [0]

    def work(a):
        rs = reviews_for(a["trackId"])
        done[0] += 1
        if done[0] % 25 == 0:
            print("  %d/%d apps, %d reviews so far" % (done[0], len(targets), len(all_reviews)))
        return rs

    with ThreadPoolExecutor(max_workers=6) as ex:
        for rs in ex.map(work, targets):
            all_reviews.extend(rs)

    print("  → %d reviews\n" % len(all_reviews))
    json.dump(all_reviews, open(os.path.join(DATA, "reviews.json"), "w", encoding="utf-8"))
    print("wrote data/apps.json and data/reviews.json")


if __name__ == "__main__":
    main()
