#!/usr/bin/env python3
"""
Unforced Error — the Apple rate-limit sitter.

itunes.apple.com/…/customerreviews serves 403 for a while after you exceed its
rate. Nothing documents how long. This polls one known-good feed every 60 s and,
the moment it returns 200, hands off to fetch_reviews.py, which is resumable and
picks up wherever the blocked run stopped.
"""
import json, os, subprocess, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = ("https://itunes.apple.com/us/rss/customerreviews/page=1/id=1547205724/"
         "sortby=mostrecent/json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")


def alive():
    try:
        req = urllib.request.Request(PROBE, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status == 200
    except Exception:
        return False


t0 = time.time()
while True:
    if alive():
        mins = (time.time() - t0) / 60
        print("unblocked after %.1f min — starting retrieval" % mins, flush=True)
        subprocess.call([sys.executable, "-u", os.path.join(HERE, "fetch_reviews.py")])
        break
    print("still 403 at %.1f min" % ((time.time() - t0) / 60), flush=True)
    time.sleep(60)
