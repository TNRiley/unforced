#!/usr/bin/env python3
"""
Unforced Error — stage 2: screening.

A systematic review screens on title and abstract before it retrieves anything,
and records a reason for every exclusion. This does the same to the app census,
so the retrieval stage only fetches reviews for apps that survived.

Two units of analysis come out of here and they must not be confused:

  * the CENSUS   — all 2,242 identified apps. Used for the market map, where
                   the long tail is the point.
  * the CORPUS   — the ~320 apps that pass every criterion. Only these have
                   their reviews retrieved and coded.

Every rule below is a published regex. They are shipped into the page verbatim
so a reader can audit the screen instead of trusting it.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# ---- the screen -------------------------------------------------------------
SPORT_RE = r"\b(tennis|padel|pickleball|pickle ?ball|squash|racquetball|racketball|badminton|ping[- ]?pong)\b"
BET_RE   = r"\b(bet(ting|s)?|odds|bookmaker|parlay|wager|prediction tips|betting tips)\b"
MIN_RATINGS = 10
DESC_CHARS = 1500          # how much of the description the screen may read

SPORT = re.compile(SPORT_RE, re.I)
BET = re.compile(BET_RE, re.I)

# Which racquet sport. Order matters: the first match that is not a generic
# "racket sports" claim wins, and an app naming three or more is "multi-sport".
SPORTS = [
    ("tennis",       r"\btennis\b(?! ?elbow)"),
    ("pickleball",   r"\bpickle ?ball\b"),
    ("padel",        r"\bpadel\b"),
    ("badminton",    r"\bbadminton\b"),
    ("table tennis", r"\b(table tennis|ping[- ]?pong)\b"),
    ("squash",       r"\bsquash\b"),
    ("racquetball",  r"\b(racquetball|racketball)\b"),
]

# What kind of app. A single app can match several; the highest-priority match
# in this order is its primary type, and the rest are kept as secondary tags.
TYPES = [
    ("scoring & stats",   r"\b(score ?keep|scorekeeper|keep score|scoring|match stats|statistics|track (your )?(match|score|stat)|point[- ]by[- ]point|match tracker|log (your )?match)\b"),
    ("live scores & news", r"\b(live scores?|livescore|results and|draws?|rankings?|atp|wta|itf|standings|fixtures|news and)\b"),
    ("coaching & training", r"\b(drill|coach|training|lesson|technique|practice plan|academy|improve your (game|serve)|workout)\b"),
    ("video & analysis",  r"\b(video analysis|slow motion|swing analysis|record your|frame[- ]by[- ]frame|ai analysis|computer vision)\b"),
    ("club, league & booking", r"\b(book a court|court booking|reserve|club member|league|ladder|tournament (management|software)|find (a )?(partner|player)|matchmaking)\b"),
    ("equipment & stringing", r"\b(string(ing|er)|tension|racquet customi|grip size|balance and swingweight)\b"),
]
SPORT_PATS = [(n, re.compile(p, re.I)) for n, p in SPORTS]
TYPE_PATS = [(n, re.compile(p, re.I)) for n, p in TYPES]


def screen_text(a):
    return (a.get("trackName", "") or "") + " \n " + ((a.get("description") or "")[:DESC_CHARS])


def classify(a):
    t = screen_text(a)
    sports = [n for n, p in SPORT_PATS if p.search(t)]
    sport = "multi-sport" if len(sports) >= 3 else (sports[0] if sports else "unclear")
    types = [n for n, p in TYPE_PATS if p.search(t)]
    return sport, sports, (types[0] if types else "other / unclassified"), types


def main():
    d = json.load(open(os.path.join(DATA, "apps.json"), encoding="utf-8"))
    apps = d["apps"]
    kept, excluded = [], []
    for a in apps:
        t = screen_text(a)
        if not SPORT.search(t):
            excluded.append((a, "off-topic — no racquet sport named"))
            continue
        if a.get("primaryGenreName") == "Games":
            excluded.append((a, "video game, not a tool for real play"))
            continue
        if BET.search(t):
            excluded.append((a, "betting / odds prediction"))
            continue
        if (a.get("userRatingCount") or 0) < MIN_RATINGS:
            excluded.append((a, "fewer than %d US ratings" % MIN_RATINGS))
            continue
        kept.append(a)

    out = {
        "identified": len(apps),
        "queries": d["queries"],
        "queryHits": d["queryHits"],
        "harvested": d["harvested"],
        "minRatings": MIN_RATINGS,
        "descChars": DESC_CHARS,
        "rules": {"sport": SPORT_RE, "betting": BET_RE,
                  "sports": SPORTS, "types": TYPES},
        "excludedCounts": {},
        "includedIds": [a["trackId"] for a in kept],
    }
    for _, r in excluded:
        out["excludedCounts"][r] = out["excludedCounts"].get(r, 0) + 1
    json.dump(out, open(os.path.join(DATA, "screen.json"), "w", encoding="utf-8"))

    print("identified        %5d" % len(apps))
    for r, n in sorted(out["excludedCounts"].items(), key=lambda kv: -kv[1]):
        print("  excluded %-38s %5d" % (r, n))
    print("INCLUDED          %5d  (%s ratings between them)"
          % (len(kept), format(sum(a["userRatingCount"] for a in kept), ",")))
    print("wrote data/screen.json")


if __name__ == "__main__":
    main()
