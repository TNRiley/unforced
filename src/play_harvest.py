#!/usr/bin/env python3
"""
Unforced Error — stage 1b: the Android arm.

The App Store gives review text away in an RSS feed. Google Play does not: the
store is a single-page app and every list is fetched by an internal RPC called
`batchexecute`. Nothing here is documented by Google; the shapes below were read
off live responses. Expect them to rot.

  search    GET  /store/search?q=<term>&c=apps
            The rendered HTML still carries every result's package name in an
            href, so the ids can be scraped without touching the RPC at all.
            ~30 results per term, which is why the query list has to be long.

  detail    GET  /store/apps/details?id=<pkg>
            Metadata lives in `AF_initDataCallback` blocks keyed ds:N. The one
            that matters is ds:5; its offsets are hard-coded in PATHS below
            because the array is positional and unnamed.

  reviews   POST /_/PlayStoreUi/data/batchexecute?rpcids=UsvDTd
            f.req carries a JSON-in-JSON payload. Response is `)]}'` + a length
            line + an array whose [0][2] is another JSON string holding
            [[review, ...], [next_page_token]]. Paginate by passing the token
            back in place of the count triple. 199 is the largest page Play
            will serve; asking for more silently returns 199.

Review tuple offsets (r[i]): 0 id, 1 author block, 2 rating, 4 text,
5 [epoch_seconds, nanos], 6 thumbs-up, 10 app version.
"""
import json, os, re, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")
THROTTLE = 0.2
PAGE = 199              # Play's real maximum per RPC call
MAX_PAGES = 3           # 597 reviews per app ceiling, matched to the iOS cap of 500

QUERIES = [
    # The 28 terms shared with the iOS harvest, so the two censuses are built
    # the same way…
    "tennis", "tennis stats", "tennis scorekeeper", "tennis score", "tennis coach",
    "tennis training", "tennis drills", "tennis live scores", "tennis match",
    "tennis club", "tennis lessons", "tennis serve", "tennis video analysis",
    "tennis ladder", "tennis rankings", "utr tennis", "usta", "atp tour", "wta",
    "padel", "pickleball", "pickleball score", "squash", "racquetball", "badminton",
    "table tennis", "racket sport", "court booking",
    # …and 26 more, because Play returns ~30 results per query where the iOS
    # Search API returns up to 200. Without these the Android census is a fifth
    # the depth of the iOS one and the two arms are not comparable. Recorded
    # separately in the payload so the asymmetry is visible rather than hidden.
    "tennis scoreboard", "tennis umpire", "tennis referee", "tennis practice",
    "tennis partner", "tennis court finder", "tennis tournament", "tennis league",
    "tennis rating", "tennis analytics", "tennis serve speed", "racquet stringing",
    "padel score", "padel booking", "pickleball rating", "pickleball tournament",
    "pickleball drills", "badminton score", "badminton tournament",
    "squash score", "table tennis score", "ping pong score",
    "racket sports booking", "sports scorekeeper", "match scoring", "dupr",
]


def _open(req, tries=4):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def http_get(url):
    return _open(urllib.request.Request(url, headers={"User-Agent": UA,
                                                      "Accept-Language": "en-US,en"}))


def search(term):
    url = ("https://play.google.com/store/search?q=%s&c=apps&hl=en&gl=us"
           % urllib.parse.quote(term))
    try:
        h = http_get(url)
    except Exception as e:
        print("  ! search %s: %s" % (term, e), file=sys.stderr)
        return []
    seen, out = set(), []
    for pkg in re.findall(r"/store/apps/details\?id=([A-Za-z0-9_.]+)", h):
        if pkg not in seen:
            seen.add(pkg)
            out.append(pkg)
    return out


# ds:5 is positional; these are the offsets that held on 2026-09-06.
PATHS = {
    "title":        (1, 2, 0, 0),
    "developer":    (1, 2, 68, 0),
    "installs":     (1, 2, 13, 0),
    "installsExact": (1, 2, 13, 2),
    "updated":      (1, 2, 10, 0),
    "score":        (1, 2, 51, 0, 1),
    "ratings":      (1, 2, 51, 2, 1),
    "reviewCount":  (1, 2, 51, 3, 1),
    # the 1..5 star histogram — Play exposes it, the iOS Search API never does
    "hist1":        (1, 2, 51, 1, 1, 1),
    "hist2":        (1, 2, 51, 1, 2, 1),
    "hist3":        (1, 2, 51, 1, 3, 1),
    "hist4":        (1, 2, 51, 1, 4, 1),
    "hist5":        (1, 2, 51, 1, 5, 1),
    "genre":        (1, 2, 79, 0, 0, 0),
    "genreId":      (1, 2, 79, 0, 0, 2),
    "description":  (1, 2, 72, 0, 1),
    "free":         (1, 2, 57, 0, 0, 0, 0, 1, 0, 0),
    "released":     (1, 2, 10, 0),
    "contentRating": (1, 2, 9, 0),
}


def dig(o, path):
    for k in path:
        try:
            o = o[k]
        except Exception:
            return None
    return o


def detail(pkg):
    url = ("https://play.google.com/store/apps/details?id=%s&hl=en&gl=us"
           % urllib.parse.quote(pkg))
    h = http_get(url)
    ds5 = None
    for b in re.findall(r"AF_initDataCallback\((\{.*?\})\);</script>", h, re.S):
        if re.search(r"key:\s*'ds:5'", b):
            m = re.search(r"data:(\[.*\]), sideChannel", b, re.S)
            if m:
                ds5 = json.loads(m.group(1))
            break
    if ds5 is None:
        return None
    rec = {"appId": pkg, "url": "https://play.google.com/store/apps/details?id=" + pkg}
    for k, p in PATHS.items():
        rec[k] = dig(ds5, p)
    return rec


def _rpc(body):
    data = urllib.parse.urlencode({"f.req": json.dumps(body)}).encode()
    url = ("https://play.google.com/_/PlayStoreUi/data/batchexecute?rpcids=UsvDTd"
           "&hl=en&gl=us&soc-app=121&soc-platform=1&soc-device=1&rt=c")
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    raw = _open(req)
    # )]}' , a length line, then the envelope
    m = re.search(r"\[\[\"wrb.fr\".*", raw, re.S)
    if not m:
        return None
    env = json.loads(m.group(0).split("\n")[0])
    inner = env[0][2] if env and env[0] and len(env[0]) > 2 else None
    return json.loads(inner) if inner else None


def reviews_for(pkg):
    out, token = [], None
    for _ in range(MAX_PAGES):
        if token is None:
            payload = [None, None, [2, 2, [PAGE, None, None], None, []], [pkg, 7]]
        else:
            payload = [None, None, [2, 2, [PAGE, None, token], None, []], [pkg, 7]]
        try:
            res = _rpc([[["UsvDTd", json.dumps(payload), None, "generic"]]])
        except Exception as e:
            print("  ! reviews %s: %s" % (pkg, e), file=sys.stderr)
            break
        time.sleep(THROTTLE)
        if not res or not res[0]:
            break
        for r in res[0]:
            try:
                out.append({
                    "id": r[0],
                    "app": pkg,
                    "rating": r[2],
                    "title": "",                       # Play has no review titles
                    "body": r[4] or "",
                    "version": r[10] or "",
                    "author": (r[1] or [None])[0] or "",
                    "epoch": (r[5] or [None])[0],
                    "votes": r[6] or 0,
                })
            except Exception:
                continue
        # last element is [next_page_token]; absent or non-string means the end
        token = None
        try:
            cand = res[-1][-1]
            if isinstance(cand, str) and cand:
                token = cand
        except Exception:
            pass
        if not token:
            break
    return out


def main():
    print("play 1a — search (%d queries)" % len(QUERIES))
    pkgs = {}
    for q in QUERIES:
        got = search(q)
        for p in got:
            pkgs.setdefault(p, []).append(q)
        time.sleep(THROTTLE)
        print("  %-22s %3d results (union %d)" % (q, len(got), len(pkgs)))
    print("  → %d distinct packages\n" % len(pkgs))

    print("play 1b — detail")
    apps, done = [], [0]

    def d(p):
        try:
            rec = detail(p)
        except Exception as e:
            print("  ! detail %s: %s" % (p, e), file=sys.stderr)
            return None
        done[0] += 1
        if done[0] % 40 == 0:
            print("  %d/%d" % (done[0], len(pkgs)))
        if rec:
            rec["_foundBy"] = pkgs[p]
        return rec

    with ThreadPoolExecutor(max_workers=6) as ex:
        for rec in ex.map(d, list(pkgs)):
            if rec:
                apps.append(rec)
    print("  → %d with metadata\n" % len(apps))
    json.dump({"apps": apps, "queries": QUERIES,
               "harvested": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
              open(os.path.join(DATA, "play_apps.json"), "w", encoding="utf-8"))

    print("stop here — screening happens in screen_play.py, retrieval in "
          "fetch_play_reviews.py, so nothing is fetched for an app that will "
          "be excluded anyway.")


if __name__ == "__main__":
    main()
