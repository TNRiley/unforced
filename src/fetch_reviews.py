#!/usr/bin/env python3
"""
Unforced Error — stage 3: retrieval (iOS).

Pulls up to 500 reviews for each app that survived screen.py, from Apple's
customer-reviews RSS feed. One file per app under data/rss/, so the run is
resumable: rerunning skips anything already on disk. That matters, because
Apple WILL rate-limit you.

Rate limiting, learned the hard way: 6 workers at 0.12 s (~50 req/s) earned a
wall of 403s within a minute. The 403 body is HTML, so it surfaces as a JSON
decode error if you are not checking status. 3 workers at 0.6 s (~5 req/s) with
exponential backoff runs clean.

Feed quirks:
  * page 1 entry[0] is the app, not a review — skip anything without im:rating
  * a feed with no reviews omits 'entry' entirely rather than returning []
  * a single-review feed returns a dict where a list is expected
  * the feed serves at most 10 pages of 50, most recent first
"""
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RSS = os.path.join(DATA, "rss")
os.makedirs(RSS, exist_ok=True)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")
WORKERS = 2
THROTTLE = 1.0   # ~2 req/s; the first attempt at ~50 req/s earned an IP ban
PAGES = 10
BACKOFF = [4, 12, 30, 60]


def get(url):
    for i, wait in enumerate([0] + BACKOFF):
        if wait:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503):
                continue                     # throttled — back off and retry
            return None                      # 404 etc: this app has no feed
        except Exception:
            continue
    return None


def fetch(tid):
    path = os.path.join(RSS, "%d.json" % tid)
    if os.path.exists(path):
        return None
    out = []
    for page in range(1, PAGES + 1):
        d = get("https://itunes.apple.com/us/rss/customerreviews/page=%d/id=%d/"
                "sortby=mostrecent/json" % (page, tid))
        time.sleep(THROTTLE)
        if not d:
            break
        entries = d.get("feed", {}).get("entry")
        if not entries:
            break
        if isinstance(entries, dict):
            entries = [entries]
        n_before = len(out)
        for e in entries:
            if "im:rating" not in e:
                continue                     # the app summary entry on page 1
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
        if len(entries) < 50 or len(out) == n_before:
            break
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f)
    return len(out)


def main():
    scr = json.load(open(os.path.join(DATA, "screen.json"), encoding="utf-8"))
    ids = scr["includedIds"]
    todo = [t for t in ids if not os.path.exists(os.path.join(RSS, "%d.json" % t))]
    print("%d included apps, %d still to fetch" % (len(ids), len(todo)))
    done = [0]

    def w(t):
        n = fetch(t)
        done[0] += 1
        if done[0] % 20 == 0:
            print("  %d/%d" % (done[0], len(todo)), flush=True)
        return n

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(w, todo))

    total = 0
    for t in ids:
        p = os.path.join(RSS, "%d.json" % t)
        if os.path.exists(p):
            total += len(json.load(open(p, encoding="utf-8")))
    print("done — %d reviews across %d files" % (total, len(os.listdir(RSS))))


if __name__ == "__main__":
    main()
