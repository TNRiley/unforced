# 🎾 Unforced Error

**19,203 app-store reviews of racquet-sport apps, screened and coded like a systematic review.**

→ **[Open it](https://tnriley.github.io/unforced/)**

Every app in the racquet-sport corner of the App Store and Google Play, found by keyword, screened against a published rule, and its reviews coded by a codebook you can edit on the page — change a regular expression and all 19,203 reviews recode. The finding: nothing that costs an app stars is a feature. Login, price, crashes and ads sit up to two stars below the corpus mean, while the topics that turn up in the happiest reviews are the ones a product manager files as complaints — doubles support, a watch app, a CSV export. People ask you for features at four and five stars. They leave one star over a login that will not take. Half the build failed and is documented: Apple 403'd its review feed and four other routes to the same text were tried and closed.

## Running it

One self-contained HTML file. No build step, no server, no network access at runtime — open `index.html` in a browser, or serve the directory with any static host.

```bash
python3 -m http.server 8000   # then visit http://localhost:8000
```

## Rebuilding it from scratch

[REBUILD.md](REBUILD.md) is written for an LLM with a shell and nothing else: the data sources and their quirks, the processing decisions, the page's structure and interactions, and a table of expected values to check the result against.

## Source

The full build pipeline is in [`src/`](src/), with a README describing how to regenerate the page from scratch.

## Data

- **[Apple iTunes Search API (app metadata, US storefront)](https://itunes.apple.com/search)** — Apple public endpoint; metadata used for research, not redistributed in bulk
- **[Apple customer-reviews RSS feed](https://itunes.apple.com/us/rss/customerreviews/)** — Apple public endpoint — returned 403 throughout this build; no review text retrieved
- **[Google Play store listings and PlayStoreUi batchexecute RPC](https://play.google.com/store/apps/)** — public store pages; review text quoted for research and attributed to its app

Every figure on the page is computed from the data shipped with it. Check the page's own methods panel for how each number is derived and where it should not be pushed.

## Built with

vanilla JS, gzip + DecompressionStream payload, canvas, inline SVG, live regex coding.

## Licence

Code is MIT (see [LICENSE](LICENSE)). Data keeps the licence of its source, listed above.

---

Part of [Quick Projects](https://github.com/TNRiley/quick-projects) — one self-contained thing, built in one session. First published 2026-09-06.
