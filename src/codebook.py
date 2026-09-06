#!/usr/bin/env python3
"""
Unforced Error — the codebook.

Every review is coded by regex, and every regex is shipped into the page so a
reader can audit it. No LLM touches a single review: a model would code more
subtly, but it could not be published, re-run, or argued with, and a codebook
you cannot argue with is not a method.

Rules of thumb used while writing these:
  * Prefer a phrase to a word. "crash" is safe; "bug" alone catches "bug me".
  * Never code on a word that appears in praise as often as in complaint.
    "update" is the worst offender — "great update!" and "broken since the
    update" are the same token.
  * A code may fire on any review of any rating. Whether a theme skews negative
    is a finding, not an assumption, so nothing here filters on stars.
  * Accept low recall. A code that fires on 6% of reviews and is right nearly
    every time is worth more than one that fires on 20% and is right two thirds
    of the time, because the page reports rates and a noisy rate is a lie.

Precision was hand-checked on a random sample per code; see calibrate.py, and
the measured numbers ride along in the payload and are printed on the page.

Six tokens were cut after the first calibration read, each for the same reason
— they fired on text that had nothing to do with the code:

  "unusable"        crashes      → "unusable due to the number of ads"
  "new phone"       lost data    → "on a new phone, the app doesn't launch"
  "not correct"     stale data   → "details are not correct" (a signup form)
  "please fix"      request      → a bug report, not a request for a feature
  "user friendly"   usability    → fired on PRAISE nine times in twenty
  bare "offline"    offline      → Indian court-booking apps discuss "offline
                                   bookings" made by phone, constantly

The last one is the instructive one. A word can be perfectly unambiguous in the
domain you imagined and mean something else entirely in the corpus you actually
have.
"""

# name, colour role, regex, one-line definition shown in the page
CODES = [
    ("crashes & freezes", "fault",
     r"\b(crash(es|ed|ing)?|freez(es|ing|e up)|force clos|keeps? closing|"
     r"wont open|won'?t open|black screen|stops? working|not working at all)\b",
     "The app stops running: crashing, freezing, refusing to open."),

    ("lost data / no sync", "fault",
     r"\b(lost (all )?(my )?(data|match|score|history|stat)|data (is )?gone|"
     r"deleted (all )?my|does ?n'?t sync|no sync|sync(ing)? (issue|problem|does)|"
     r"didn'?t save|does ?n'?t save|not saving|lost everything|start(ing)? (all )?over|"
     r"history (is )?gone|restore (my|the) (data|match|purchase)|back ?up my)\b",
     "Work the user had already done disappeared, or never reached their other device."),

    ("login & account", "fault",
     r"\b(can'?t (log ?in|sign ?in)|cannot (log ?in|sign ?in)|log ?in (issue|problem|loop|fail)|"
     r"sign ?in (issue|problem|fail)|password (reset|never|does ?n'?t)|verify my email|"
     r"account (was )?(locked|deleted|disappeared))\b",
     "The user could not get into their own account."),

    ("wrong or stale data", "fault",
     r"\b(wrong (score|result|ranking|time|data)|incorrect (score|result|ranking|data)|"
     r"inaccurate|not updat(ing|ed)|does ?n'?t updat|out of date|scores? (are )?(delayed|behind|late)|"
     r"missing (match|score|result|player)s?|wrong (info|information)|"
     r"stats? (are|is) wrong|shows the wrong)\b",
     "The numbers the app shows do not match reality."),

    ("price & subscription", "money",
     r"\b(subscription|subscribe to use|paywall|free trial|charged (me|twice|again)|"
     r"refund|too expensive|overpriced|per (month|year)|monthly fee|pay ?wall|"
     r"used to be free|now you have to pay|money grab)\b",
     "What it costs, how it is charged, or what got moved behind a payment."),

    ("ads", "money",
     r"\b(ads?\b|advert|commercials|pop ?up ads|ad[- ]free|so many ads|full ?screen ads)\b",
     "Advertising: how much, how intrusive, or wanting rid of it."),

    ("feature request", "want",
     r"(\b(please|pls|plz) (add|include|make|allow|bring)|\bwould (be )?(nice|love|like) (if|to have)|"
     r"\bwish (it|there|you)|\bhope(fully)? (you|they) (add|will add)|\bneeds? to have\b|"
     r"\bmy only (wish|request|suggestion)|\bsuggestion:|\bit would be (great|nice|helpful) if)",
     "The user explicitly asks for something the app does not do."),

    ("usability & layout", "craft",
     r"\b(confusing|hard to (use|navigate|figure)|not intuitive|un ?intuitive|clunky|"
     r"cluttered|too many (taps|clicks|steps)|awkward to use|"
     r"cant figure out|can'?t figure out|unreadable|too complicated|"
     r"hard to read|messy (layout|interface|ui))\b",
     "The app works, but using it is a chore."),

    ("watch & wearable", "surface",
     r"\b(apple ?watch|wear ?os|watch app|watch face|on my watch|smartwatch|garmin|fitbit|"
     r"watch version|watch complication)\b",
     "The wrist. A companion watch app, wanted or broken."),

    ("offline & connectivity", "fault",
     r"\b(offline (mode|use|access|support)|works? offline|use it offline|"
     r"no internet|without (internet|wifi|service|signal)|"
     r"connection (error|issue|problem|lost)|server (error|down|issue)|keeps? loading|"
     r"stuck (on )?loading|spinning wheel)\b",
     "It needs the network, and the network is not always there — courts have bad signal."),

    ("battery & speed", "craft",
     r"\b(battery (drain|life|dies)|drains? (my )?battery|so slow|very slow|laggy|lags?\b|"
     r"sluggish|takes forever to load|slow to load)\b",
     "Performance: speed, lag, and what it costs the battery."),

    ("notifications", "craft",
     r"\b(notification|alerts?\b|push notif|notify me|spam(ming)? me)\b",
     "Alerts: too many, too few, or for the wrong thing."),

    ("video & streaming", "surface",
     r"\b(stream(ing)?|buffer(ing)?|chromecast|cast to|airplay|video quality|"
     r"watch (the )?(match|live)|blackout)\b",
     "Watching, not playing: live video, casting, blackouts."),

    ("support & responses", "craft",
     r"\b(no (response|reply) from|customer (support|service)|contacted (support|them|the developer)|"
     r"support (never|does ?n'?t|won'?t)|no one (replies|responds)|unresponsive developer)\b",
     "What happened when the user tried to reach a human."),

    ("scoring & stats depth", "want",
     r"\b(keep(ing)? score|score ?keep|point by point|match stats|statistics|"
     r"serve percentage|first serve|unforced error|winners? and errors?|"
     r"track (my )?(match|stat|progress)|stat(s)? (are|is) (basic|limited|shallow))\b",
     "The thing a scorekeeper exists to do — and how deep it goes."),

    ("doubles & multiplayer", "want",
     r"\b(doubles|mixed doubles|two players|both teams|partner'?s? (stat|score)|"
     r"multiple players|team match|league play)\b",
     "Tennis is played by four people as often as two, and software forgets."),

    ("export & sharing", "want",
     r"\b(export|csv|spreadsheet|pdf|share (my |the )?(match|stat|score|result)|"
     r"print (out|the)|email (the |my )?(result|stat|match)|download my data)\b",
     "Getting the data back out of the app."),

    ("praise", "good",
     r"\b(love (this|the) app|best (tennis |pickleball |padel )?app|works? (great|perfectly|flawlessly)|"
     r"exactly what i (was looking for|needed|wanted)|highly recommend|"
     r"easy to use|simple and|does everything i)\b",
     "A control code. If a theme is worded so loosely that it fires alongside praise, it is wrong."),
]

ROLE_ORDER = ["fault", "money", "want", "craft", "surface", "good"]
