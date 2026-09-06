# src — the build pipeline

Nine scripts, no dependencies beyond the standard library. Run them in the order in
[`../REBUILD.md`](../REBUILD.md), which also carries the endpoint quirks, the array
offsets, and the verification table.

| file | what it does |
|---|---|
| `harvest.py` | iOS census from the iTunes Search API, then reviews from the RSS feed |
| `screen.py` | the screening criteria, shared by both stores; writes `data/screen.json` |
| `play_harvest.py` | Play census: search-page scrape → `ds:5` metadata; also holds the reviews RPC |
| `screen_play.py` | the same criteria against Play's fields, incl. the `genreId` game flag |
| `fetch_reviews.py` | iOS review retrieval, resumable, one file per app |
| `fetch_play_reviews.py` | the same for Play |
| `await_apple.py` | polls Apple's 403 and starts `fetch_reviews.py` the moment it lifts |
| `codebook.py` | the 18 codes, as regexes, with the six tokens calibration removed |
| `calibrate.py` | writes 20 random hits per code for a human to read |
| `build_payload.py` | joins both stores, gzips, base64s → `data/payload.b64` |
| `inject.py` | splices the payload into `template.html`, then wraps for Pages |

`data/` is gitignored: the raw harvest is ~20 MB and the scripts refetch it. Everything
under it is reproducible from the scripts above except what the stores have since changed.

**If you change `codebook.py`, run `calibrate.py` and read the sample.** Six of the
original tokens looked obviously right and were obviously wrong the moment twenty real
reviews were put in front of them.
