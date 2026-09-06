#!/usr/bin/env python3
"""
Unforced Error — stage 4: the payload.

Joins both stores into one structure and writes data/payload.json, plus a
gzipped base64 copy the page inflates with DecompressionStream. Review text does
not compress well per-review but compresses ~4x in bulk, which is the difference
between a page that ships and one that does not.

Two units of analysis go in, kept separate on purpose:
  census  — every app identified, both stores. Metadata only, no reviews. This
            is the market map; the long tail is the point of it.
  corpus  — the screened apps and their retrieved reviews. Everything coded.

Nothing is coded here. The codebook ships as regex source and the page runs it,
so a reader can edit a pattern and watch every number move. Coding in Python
would have been faster and would have made the page a picture of an analysis
instead of the analysis itself.
"""
import base64, gzip, json, os, re, sys, time
from codebook import CODES, ROLE_ORDER
from screen import classify, SPORT_RE, BET_RE, MIN_RATINGS, DESC_CHARS, SPORTS, TYPES

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
MAX_TEXT = 1400          # longest review body kept; p99 is far below this


def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def ios():
    """(census rows, corpus apps, reviews) from the App Store harvest."""
    ap = os.path.join(DATA, "apps.json")
    if not os.path.exists(ap):
        return [], [], []
    d = json.load(open(ap, encoding="utf-8"))
    scr = json.load(open(os.path.join(DATA, "screen.json"), encoding="utf-8"))
    inc = set(scr["includedIds"])
    census, corpus, revs = [], [], []
    for a in d["apps"]:
        sport, sports, typ, types = classify(a)
        row = {
            "store": "ios", "id": str(a["trackId"]), "name": clean(a.get("trackName")),
            "dev": clean(a.get("sellerName")), "sport": sport, "type": typ,
            "genre": a.get("primaryGenreName"),
            "n": a.get("userRatingCount") or 0,
            "score": round(a["averageUserRating"], 2) if a.get("averageUserRating") else None,
            "url": a.get("trackViewUrl"),
            "released": (a.get("releaseDate") or "")[:10],
            "updated": (a.get("currentVersionReleaseDate") or "")[:10],
            "price": a.get("price"),
            "included": a["trackId"] in inc,
        }
        census.append(row)
        if a["trackId"] in inc:
            corpus.append(row)
    for a in corpus:
        p = os.path.join(DATA, "rss", "%s.json" % a["id"])
        if not os.path.exists(p):
            continue
        for r in json.load(open(p, encoding="utf-8")):
            body = clean(r["title"] + " — " + r["body"]).strip(" —")
            revs.append({"app": a["id"], "store": "ios", "r": r["rating"],
                         "y": int((r.get("updated") or "0000")[:4]) or None,
                         "v": r.get("version") or "", "t": body[:MAX_TEXT]})
    return census, corpus, revs


def play():
    ap = os.path.join(DATA, "play_apps.json")
    if not os.path.exists(ap):
        return [], [], []
    d = json.load(open(ap, encoding="utf-8"))
    scr = json.load(open(os.path.join(DATA, "screen_play.json"), encoding="utf-8"))
    inc = set(scr["includedIds"])
    census, corpus, revs = [], [], []
    for a in d["apps"]:
        shim = {"trackName": a.get("title"), "description": a.get("description")}
        sport, sports, typ, types = classify(shim)
        row = {
            "store": "play", "id": a["appId"], "name": clean(a.get("title")),
            "dev": clean(a.get("developer")), "sport": sport, "type": typ,
            "genre": a.get("genre"),
            "n": a.get("ratings") or 0,
            "score": round(a["score"], 2) if a.get("score") else None,
            "url": a.get("url"),
            "released": a.get("released") or "", "updated": a.get("updated") or "",
            "installs": a.get("installs"),
            "included": a["appId"] in inc,
        }
        h = [a.get("hist%d" % i) for i in range(1, 6)]
        if all(isinstance(x, int) for x in h):
            row["hist"] = h
        census.append(row)
        if a["appId"] in inc:
            corpus.append(row)
    for a in corpus:
        p = os.path.join(DATA, "play_rss", "%s.json" % a["id"])
        if not os.path.exists(p):
            continue
        for r in json.load(open(p, encoding="utf-8")):
            y = None
            if r.get("epoch"):
                y = int(time.strftime("%Y", time.gmtime(r["epoch"])))
            revs.append({"app": a["id"], "store": "play", "r": r["rating"],
                         "y": y, "v": r.get("version") or "",
                         "t": clean(r["body"])[:MAX_TEXT]})
    return census, corpus, revs


def main():
    ic, ia, ir = ios()
    pc, pa, pr = play()
    census = ic + pc
    corpus = ia + pa
    reviews = [r for r in (ir + pr) if r["t"]]

    # An app that was screened IN but whose reviews could not be retrieved is not
    # part of the coded corpus. Apple 403'd its review feed for the whole of this
    # build, so all 320 screened iOS apps sit here. They stay in the census — the
    # market map is the poorer without them — but they must not be counted as
    # apps whose reviews were read.
    have = set(r["store"] + ":" + r["app"] for r in reviews)
    unretrieved = [a for a in corpus if a["store"] + ":" + a["id"] not in have]
    corpus = [a for a in corpus if a["store"] + ":" + a["id"] in have]

    idx = {a["store"] + ":" + a["id"]: i for i, a in enumerate(corpus)}
    packed = [[idx[r["store"] + ":" + r["app"]], r["r"], r["y"] or 0, r["t"]]
              for r in reviews if r["store"] + ":" + r["app"] in idx]

    scr_i = json.load(open(os.path.join(DATA, "screen.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(DATA, "screen.json")) else None
    scr_p = json.load(open(os.path.join(DATA, "screen_play.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(DATA, "screen_play.json")) else None

    payload = {
        "built": time.strftime("%Y-%m-%d"),
        "harvested": (scr_p or scr_i or {}).get("harvested", ""),
        "codes": [{"name": n, "role": role, "re": pat, "def": d} for n, role, pat, d in CODES],
        "roleOrder": ROLE_ORDER,
        "screen": {
            "sportRe": SPORT_RE, "betRe": BET_RE,
            "minRatings": MIN_RATINGS, "descChars": DESC_CHARS,
            "sports": SPORTS, "types": TYPES,
            "ios": {"identified": (scr_i or {}).get("identified", 0),
                    "excluded": (scr_i or {}).get("excludedCounts", {}),
                    "queries": (scr_i or {}).get("queries", []),
                    "included": len(ia), "reviews": len(ir),
                    "apps": len([a for a in corpus if a["store"] == "ios"])},
            "play": {"identified": (scr_p or {}).get("identified", 0),
                     "excluded": (scr_p or {}).get("excludedCounts", {}),
                     "queries": (scr_p or {}).get("queries", []),
                     "included": len(pa), "reviews": len(pr),
                     "apps": len([a for a in corpus if a["store"] == "play"])},
            "unretrieved": len(unretrieved),
        },
        "apps": corpus,
        "census": census,
        "reviews": packed,
    }

    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    gz = gzip.compress(raw, 9)
    b64 = base64.b64encode(gz).decode("ascii")
    open(os.path.join(DATA, "payload.json"), "w", encoding="utf-8", newline="\n").write(
        raw.decode("utf-8"))
    open(os.path.join(DATA, "payload.b64"), "w", encoding="utf-8", newline="\n").write(b64)
    print("census %d apps · screened-in %d · retrieved %d apps · %d reviews"
          % (len(census), len(corpus) + len(unretrieved), len(corpus), len(packed)))
    if unretrieved:
        print("  %d screened-in apps had no reviews retrieved (%s)"
              % (len(unretrieved),
                 ", ".join(sorted(set(a["store"] for a in unretrieved)))))
    print("raw %.1f MB → gzip %.1f MB → base64 %.1f MB"
          % (len(raw) / 1e6, len(gz) / 1e6, len(b64) / 1e6))


if __name__ == "__main__":
    main()
