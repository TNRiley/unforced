#!/usr/bin/env python3
"""
Unforced Error — codebook calibration.

Draws a random sample of the reviews each code fires on and writes them out for
a human to mark right or wrong. The verdicts go back into calibration.json and
are shipped into the page, so every rate on it carries a measured precision
rather than an implied one.

  python3 calibrate.py sample   → data/calibration_sample.txt  (to be marked)
  python3 calibrate.py score    → reads data/calibration_marks.json, prints table

A code whose precision falls below ~0.8 gets rewritten, not published.
"""
import json, glob, os, random, re, sys
from codebook import CODES

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PER_CODE = 20
SEED = 20260906


def corpus():
    out = []
    ip = os.path.join(DATA, "screen_play.json")
    if os.path.exists(ip):
        inc = set(json.load(open(ip, encoding="utf-8"))["includedIds"])
        for f in glob.glob(os.path.join(DATA, "play_rss", "*.json")):
            if os.path.basename(f)[:-5] in inc:
                for r in json.load(open(f, encoding="utf-8")):
                    r["store"] = "play"
                    out.append(r)
    ii = os.path.join(DATA, "screen.json")
    if os.path.exists(ii):
        inc = set(str(x) for x in json.load(open(ii, encoding="utf-8"))["includedIds"])
        for f in glob.glob(os.path.join(DATA, "rss", "*.json")):
            if os.path.basename(f)[:-5] in inc:
                for r in json.load(open(f, encoding="utf-8")):
                    r["store"] = "ios"
                    out.append(r)
    return out


def main():
    rs = corpus()
    print("corpus %d" % len(rs), file=sys.stderr)
    rnd = random.Random(SEED)
    lines = []
    for name, role, pat, desc in CODES:
        p = re.compile(pat, re.I)
        hits = [r for r in rs if p.search(r["title"] + " " + r["body"])]
        samp = rnd.sample(hits, min(PER_CODE, len(hits)))
        lines.append("\n##### %s   (fires on %d)" % (name, len(hits)))
        for i, r in enumerate(samp):
            t = (r["title"] + " — " + r["body"]).strip(" —").replace("\n", " ")
            lines.append("%02d [%d★ %s] %s" % (i, r["rating"], r["store"], t[:230]))
    open(os.path.join(DATA, "calibration_sample.txt"), "w",
         encoding="utf-8", newline="\n").write("\n".join(lines))
    print("wrote data/calibration_sample.txt")


if __name__ == "__main__":
    main()
