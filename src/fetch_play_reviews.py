#!/usr/bin/env python3
"""
Unforced Error — stage 3b: retrieval (Android).

Resumable like the iOS side: one file per package under data/play_rss/.
Play tolerates a far higher request rate than Apple, but there is no reason to
push it — 4 workers is plenty for a few hundred packages.
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import play_harvest as P

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(DATA, "play_rss")
os.makedirs(OUT, exist_ok=True)


def main():
    scr = json.load(open(os.path.join(DATA, "screen_play.json"), encoding="utf-8"))
    ids = scr["includedIds"]
    todo = [p for p in ids if not os.path.exists(os.path.join(OUT, p + ".json"))]
    print("%d included packages, %d to fetch" % (len(ids), len(todo)), flush=True)
    done = [0]

    def w(pkg):
        try:
            rs = P.reviews_for(pkg)
        except Exception as e:
            print("  ! %s %s" % (pkg, e), file=sys.stderr)
            rs = []
        with open(os.path.join(OUT, pkg + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(rs, f)
        done[0] += 1
        if done[0] % 20 == 0:
            print("  %d/%d" % (done[0], len(todo)), flush=True)
        return len(rs)

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(w, todo))
    total = sum(len(json.load(open(os.path.join(OUT, p + ".json"), encoding="utf-8")))
                for p in ids if os.path.exists(os.path.join(OUT, p + ".json")))
    print("done — %d reviews across %d packages" % (total, len(os.listdir(OUT))))


if __name__ == "__main__":
    main()
