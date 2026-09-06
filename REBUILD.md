# Rebuilding Unforced Error

For an LLM with a shell and no other context. This is a recipe, not a summary.

## What is being built

A single self-contained HTML page over the racquet-sport corner of the two mobile app
stores. Every app is found by keyword search, screened against published criteria with a
recorded reason for each exclusion, and the reviews of the survivors are coded by a
codebook of regular expressions that **ships as source and runs in the browser** — the
reader edits a pattern and all ~19,000 reviews recode in place.

**The finding the page exists to show.** Sort the topics by the mean star rating of the
reviews they appear in and they split cleanly in two. Everything that drags an app below
the corpus mean is infrastructure — login (1.31★), price and subscription (1.51★),
crashes (1.69★), connectivity, speed, ads. Everything *above* the mean is a request:
export and sharing, doubles support, feature requests generally, scoring depth, and a
watch app at 4.23★. **People ask you for features at four and five stars, and leave one
star over a login that will not take.** The chart is a lollipop per topic against a 1–5
star axis with the selection's own mean as the reference line, and that is the whole
argument in one picture.

## Data sources, with the quirks that will bite

### Apple — census only, and here is why

* `https://itunes.apple.com/search?term=<q>&entity=software&country=us&limit=200`
  No key. Returns full metadata already attached: `trackId`, `trackName`, `sellerName`,
  `primaryGenreName`, `userRatingCount` (**US only**), `averageUserRating` (lifetime, all
  versions), `description`, `releaseDate`, `currentVersionReleaseDate`, `trackViewUrl`.
  28 query terms → **2,242 distinct apps**, ~19 MB of JSON.

* `https://itunes.apple.com/us/rss/customerreviews/page=<1..10>/id=<trackId>/sortby=mostrecent/json`
  50 reviews a page, ten pages, so **500 per app is the hard ceiling**. Quirks:
  page 1's `entry[0]` is the *app*, not a review (skip anything with no `im:rating`);
  a feed with no reviews omits `entry` entirely rather than returning `[]`; a
  single-review feed returns a dict where a list belongs.

  **This endpoint 403'd for the entire build.** It tolerates roughly five requests a
  second. The first harvest ran six threads 0.12 s apart — about fifty a second — and was
  cut off within a minute, for the whole endpoint, for over an hour. The 403 body is
  HTML, so without a status check it surfaces as a JSON decode error and reads like a bug
  in your own code. `src/await_apple.py` polls one known-good feed every 60 s and starts
  `fetch_reviews.py` the moment it returns 200; that script is resumable (one file per
  app under `data/rss/`), so the run picks up wherever it stopped.

  Four alternate routes were tried and **all four are closed**:
  the older `itunes.apple.com/rss/customerreviews/id=…` path (same block — it is the
  endpoint, not the URL); `amp-api.apps.apple.com/v1/catalog/us/apps/<id>/reviews`
  (`401`; it wants `Bearer $MEDIA_API_TOKEN`, which the front end reads from
  `process.env` and which is in neither `apps.apple.com`'s HTML nor either of its two
  script bundles); the product page's `serialized-server-data`, which does carry reviews
  but **only eight**, chosen by Apple for being helpful — a highlight reel, not a sample,
  and mixing it with 597 unfiltered Play reviews would make any store comparison an
  artefact; and `?see-all=reviews`, which renders client-side and ships none of it.

  If you rebuild and Apple answers, you get the two-store comparison this was designed
  for. Everything downstream already handles it.

### Google Play — census and corpus

Nothing here is documented by Google; the shapes were read off live responses.

* **search** `https://play.google.com/store/search?q=<q>&c=apps&hl=en&gl=us`
  The rendered HTML still carries every result's package name in an
  `/store/apps/details?id=…` href, so ids can be scraped without touching the RPC.
  **~30 results per query**, against Apple's 200 — this asymmetry is the single most
  important thing to know about the two arms. The Play query list was extended to 54
  terms to compensate and still finds a shallower census. **Compare rates, never totals.**

* **detail** `https://play.google.com/store/apps/details?id=<pkg>&hl=en&gl=us`
  Metadata lives in `AF_initDataCallback` blocks keyed `ds:N`; the one that matters is
  `ds:5`. It is a positional, unnamed array, so the offsets are hard-coded in
  `PATHS` in `src/play_harvest.py`. Verified 2026-09-06:

  | field | path |
  |---|---|
  | title | `(1,2,0,0)` |
  | developer | `(1,2,68,0)` |
  | installs | `(1,2,13,0)` |
  | updated | `(1,2,10,0)` |
  | score | `(1,2,51,0,1)` |
  | ratings | `(1,2,51,2,1)` |
  | review count | `(1,2,51,3,1)` |
  | 1★–5★ histogram | `(1,2,51,1,<1..5>,1)` |
  | **genreId** | `(1,2,79,0,0,2)` |
  | description | `(1,2,72,0,1)` |

* **reviews** `POST https://play.google.com/_/PlayStoreUi/data/batchexecute?rpcids=UsvDTd&hl=en&gl=us&rt=c`
  `f.req=[[["UsvDTd", "<json string>", null, "generic"]]]` where the inner payload is
  `[null,null,[2,2,[199,null,<token|null>],null,[]],["<pkg>",7]]`. The response is
  `)]}'`, a length line, then an array whose `[0][2]` is *another* JSON string holding
  `[[review, …],[next_page_token]]`. **199 is the real maximum**; asking for more
  silently returns 199. Three calls → **597 reviews per app**. Review tuple offsets:
  `0` id, `1[0]` author, `2` rating, `4` text, `5[0]` epoch seconds, `6` thumbs-up,
  `10` app version. Play has **no review titles**. Guard the token: after the last page
  `res[-1][-1]` is not a string, and re-sending a `null` token restarts page 1 forever.

## The screen

Applied to the app name plus the first **1,500 characters** of the description.

1. names a racquet sport — `\b(tennis|padel|pickleball|pickle ?ball|squash|racquetball|racketball|badminton|ping[- ]?pong)\b`
2. is not a video game
3. is not a betting product — `\b(bet(ting|s)?|odds|bookmaker|parlay|wager|prediction tips|betting tips)\b`
4. has **≥ 10 ratings**

**Criterion 2 is the trap.** On Apple, `primaryGenreName == "Games"` works. On Play the
*displayed* genre is useless: Play files **Tennis Clash** under "Sports", exactly like a
real scorekeeper. Screening on it put twenty video games — Tennis Clash, 3D Tennis,
Badminton League, Table Tennis 3D, Ping Pong Fury — into the **top thirty-five of the
corpus**, at 597 reviews each. The machine-readable `genreId` is the honest flag: every
game carries `GAME_*`, every app a bare category id. That one fix cut the Android corpus
from 115 apps / 29,112 reviews to 79 apps / 14,598 reviews, and everything before it was
measuring complaints about pay-to-win matchmaking.

Two units of analysis come out and must not be confused: the **census** (every identified
app, metadata only — the market map, where the tail is the point) and the **corpus** (the
screened apps whose reviews were actually retrieved). An app screened *in* whose reviews
could not be fetched belongs to neither; all 320 iOS apps are in that state.

## The codebook

18 codes, each a regex, in `src/codebook.py`, shipped verbatim into the payload and
compiled in the browser. No model reads a review: a model would code more subtly but you
could not publish it, re-run it, or argue with it.

**Codes are topics, not verdicts.** A code fires at any star rating; nothing filters on
sentiment, because sentiment is the measurement. `praise` is in the codebook as a
*control* — if a topic's wording is loose enough to fire alongside "love this app", its
mean drifts toward the corpus mean and the code is wrong.

`calibrate.py sample` writes 20 random hits per code for a human to read. That read cut
six tokens, each for firing on text with nothing to do with the code:

| token | code | what it actually caught |
|---|---|---|
| `unusable` | crashes | "unusable due to the number of ads" |
| `new phone` | lost data | "on a new phone, the app doesn't launch" |
| `not correct` | stale data | a signup form, not a score |
| `please fix` | feature request | a bug report |
| `user friendly` | usability | **praise**, nine times in twenty |
| bare `offline` | offline | Indian court-booking apps discuss "offline bookings", made by telephone, constantly |

The last is the lesson worth keeping: *a word can be unambiguous in the domain you
imagined and mean something else entirely in the corpus you actually have.* Re-run
`calibrate.py` after any codebook change and read the sample; do not skip it.

## The page

Full-bleed, desktop-first, with an in-page Auto/Light/Dark switch applied pre-paint from
`localStorage` (never trust the host to stamp a theme). Hard-court blue is the accent;
clay marks topics that cost stars, court blue those that earn them, grass the control
code. Barlow Condensed for display, Barlow for data, Newsreader for review text — reviews
are testimony and set as such. Sections are marked **15 · 30 · 40 · Game**.

Layout: PRISMA-shaped funnel → thesis + lollipop chart → three-column bench (codebook |
filters + star histogram | review reader) → market map (canvas, 2,922 apps, log ratings ×
mean score, filled = in the corpus) → sortable table → methods.

Two engineering points that matter:

* **Bitmask coding.** `MASK` is an `Int32Array`, one bit per code per review. Editing one
  pattern re-runs *only that bit* — about 150 ms — where a full 18-pattern sweep would be
  seconds. This is what makes the codebook feel live.
* **Payload.** 3.2 MB of JSON → gzip → base64 → **1.2 MB inline**, inflated with
  `DecompressionStream("gzip")`. Raw JSON would also fit under the artifact cap today but
  will not once Apple's arm lands.
* The review list **round-robins across apps**. Reviews arrive grouped by app, so the
  first 400 of anything are one developer's morning.

## Verification table

Rebuild and check these. They catch parse errors instantly.

| check | expected |
|---|---|
| iOS census, 28 queries | **2,242** distinct apps |
| iOS screened in | **320** (1,215 under 10 ratings, 507 off-topic, 185 games, 15 betting) |
| Play census, 54 queries | **413** packages |
| Play screened in | **79** with the `genreId` fix (**115** without — if you get 115, the fix is missing) |
| Play reviews retrieved | **14,598** across 79 apps; **19,203** in the shipped corpus after the query list was widened to 104 apps |
| largest per-app review count | exactly **597** (3 × 199), never more |
| corpus mean rating, multi-sport excluded | **3.41★** on the 79-app corpus; **3.56★** on the shipped 104-app one |
| `login & account` | lowest mean of any topic, **≈1.3★** |
| `watch & wearable` | highest non-control mean, **≈4.2★** |
| `praise` control | **≈4.7★** — if it drops near the corpus mean, a code is leaking |
| median review length | **59 characters** — most reviews say nothing |
| Baseline Metrics (`com.baseline.metrics`) | present in the Play census, screened **out** (under 10 ratings), Sports/`SPORTS`, released Jun 25 2026 |
| star histogram | U-shaped: 5★ and 1★ both large, 2★–3★ small |

## What the page must say about itself

* The coded corpus is **Google Play only**, and Android and iOS user bases differ.
* **Reviewers are not users** — the silent middle is absent by construction.
* Only the recent tail is reachable (500 / 597 per app). For big apps that is months; for
  a small one it is its whole life.
* Apple's rating count is **US-only**, Play's is **worldwide**.
* Multi-sport aggregators (ESPN, Sofascore, 365Scores, LiveScore, Flashscore) matched
  because their listings mention tennis; most of their reviews are about football. They
  are **excluded by default** and toggleable.
* **English only** — both harvests used the US storefront; no code will ever fire on the
  Spanish and Hindi reviews sitting in the corpus.
* Play's search asymmetry (30 vs 200 per query) means the two censuses are not equally
  deep. Compare rates, not totals.

## Order of operations

```bash
python3 src/harvest.py            # iOS census (+ reviews, if Apple is answering)
python3 src/screen.py             # iOS screen  → data/screen.json
python3 src/play_harvest.py       # Play census → data/play_apps.json
python3 src/screen_play.py        # Play screen → data/screen_play.json
python3 src/fetch_play_reviews.py # Play reviews, resumable → data/play_rss/
python3 src/await_apple.py &      # sits out the 403, then runs fetch_reviews.py
python3 src/calibrate.py          # sample for the hand read — do not skip
python3 src/build_payload.py      # → data/payload.json and data/payload.b64
python3 src/inject.py             # → index.html, wrapped and breadcrumbed
```

`inject.py` runs `catalog/tools/wrap_for_pages.py` and `add_catalog_link.py` last.
Skipping them leaves an Artifact fragment, which GitHub Pages renders in quirks mode with
every em dash and emoji as mojibake.
