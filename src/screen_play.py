#!/usr/bin/env python3
"""
Unforced Error — stage 2b: screening the Android census.

Identical criteria to screen.py, applied to Play's fields. Keeping the rules in
one place matters: the whole point of the two-store comparison is that any
difference in what users complain about is a difference in the *users*, not a
difference in how the two corpora were built.

One criterion cannot be held identical. Play does not publish a US-only rating
count, so `ratings` here is worldwide where iOS `userRatingCount` is US-only.
The page says so.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from screen import SPORT, BET, MIN_RATINGS, DESC_CHARS

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# Play's DISPLAY genre is useless for this: it labels Tennis Clash "Sports",
# exactly like a real scorekeeper. The machine-readable genreId is the reliable
# flag — every game carries GAME_*, every app carries a bare category id. Missing
# it from the first screen let 20 video games into the top 35 of the corpus.
GAME_PREFIX = "GAME"


def screen_text(a):
    return (a.get("title") or "") + " \n " + ((a.get("description") or "")[:DESC_CHARS])


def main():
    d = json.load(open(os.path.join(DATA, "play_apps.json"), encoding="utf-8"))
    apps = d["apps"]
    kept, counts = [], {}
    for a in apps:
        t = screen_text(a)
        if not SPORT.search(t):
            counts["off-topic — no racquet sport named"] = counts.get("off-topic — no racquet sport named", 0) + 1
            continue
        if (a.get("genreId") or "").startswith(GAME_PREFIX):
            counts["video game, not a tool for real play"] = counts.get("video game, not a tool for real play", 0) + 1
            continue
        if BET.search(t):
            counts["betting / odds prediction"] = counts.get("betting / odds prediction", 0) + 1
            continue
        if (a.get("ratings") or 0) < MIN_RATINGS:
            k = "fewer than %d ratings" % MIN_RATINGS
            counts[k] = counts.get(k, 0) + 1
            continue
        kept.append(a)

    out = {"identified": len(apps), "queries": d["queries"], "harvested": d["harvested"],
           "excludedCounts": counts, "includedIds": [a["appId"] for a in kept]}
    json.dump(out, open(os.path.join(DATA, "screen_play.json"), "w", encoding="utf-8"))
    print("identified        %5d" % len(apps))
    for r, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("  excluded %-38s %5d" % (r, n))
    print("INCLUDED          %5d" % len(kept))


if __name__ == "__main__":
    main()
