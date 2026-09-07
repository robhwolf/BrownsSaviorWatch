# Cleveland Browns Savior Watch

A static page tracking ten college quarterbacks who could plausibly be in the
2027 draft conversation, plus the news that actually matters about them.

```
index.html      the dashboard (reads data.json, no build step)
fetch_data.py   pulls the data, writes data.json
data.json       current snapshot — placeholder until the first real run
banner.jpg      the 3:1 masthead image
PRODUCT.md      durable product context (impeccable init)
DESIGN.md       the visual system this page is built to
.github/workflows/update.yml   the schedule
```

## Setup

1. Push this to a GitHub repo. Settings → Pages → deploy from `main`, root.
2. Get a free CFBD API key at https://collegefootballdata.com/key, then upgrade
   to Patreon Tier 2 ($5/mo, 30,000 calls) — the free tier's 1,000 calls/month
   won't survive a season at this cadence.
3. Repo Settings → Secrets and variables → Actions → new secret `CFBD_API_KEY`.
4. Actions tab → "Update Savior Watch" → Run workflow, to prove it end to end.

Run it locally with `CFBD_API_KEY=xxx python3 fetch_data.py` — no dependencies
beyond the standard library.

## The schedule

Hourly on Saturdays from noon ET through 3am ET Sunday, three times a day
otherwise. GitHub's cron is best-effort — runs get delayed by several minutes
under load, and can be skipped entirely during heavy periods. The page shows
how old the data actually is rather than claiming it's current.

Scheduled workflows are also disabled automatically after 60 days of no repo
activity. The bot's own commits count as activity, so this only bites in the
offseason.

## Eight tabs, "Board" first

Atop the page: a 3:1 banner image, then a tab bar. **Board** is the first tab
and the default view — all ten quarterbacks as pinned nameplates with a photo,
ranked by Kalshi's live first-pick odds where the market has an opinion
(untracked-by-the-market names keep their original order). Clicking a
nameplate jumps straight to that player's card. Everything else lives behind
the same tab bar, one panel visible at a time:

1. **Board** — the ranked nameplate grid described above.
2. **Live** — only the quarterbacks currently playing, with quarter, clock,
   score and a live stat line. When nobody's playing it collapses to a single
   line naming the next kickoff.
3. **This week** — everyone else. Finals first, then whoever hasn't kicked off.
4. **Next game** — every tracked QB's next kickoff, soonest first.
5. **Season** — cumulative totals, sortable by passer rating, yards, total
   touchdowns, yards per attempt, completion percentage, EPA per play, or
   fewest interceptions. Whoever leads the current sort is highlighted.
6. **Market odds** — Kalshi's live implied probabilities for three markets:
   first player picked, first team to pick, and Heisman winner. Shown as a
   plain ranked list (top 8 plus a "Field" bucket for the rest) — no charts,
   just the current price. Informational only, not a recommendation to trade.
7. **News** — the ranked, source-and-freshness-scored headline list.
8. **Reading** — Wikipedia, official university bio, and ESPN profile for each
   tracked quarterback. Verified by hand against each source (no guessed
   URLs); these live in `fetch_data.py`'s `REFERENCES` dict, not fetched live,
   so they need updating by hand if a link changes.

Visual design decisions — palette, type, the pin device, the whole "big board"
direction — are recorded in [DESIGN.md](DESIGN.md).

## How season totals are built

Totals are accumulated locally rather than pulled as season stats. Each time a
game goes final, its box score line is appended to that quarterback's game log
in `data.json`, keyed on ESPN's event id so reruns overwrite rather than
double-count. Season numbers are then summed from the log.

This means a bad API response can't wipe out weeks of history, the totals stay
consistent with the per-game numbers on screen, and you get a week-by-week log
for free — the `log` array is in the data if you want to chart trends later.

Passer rating uses the NCAA formula:
`(8.4·yards + 330·TD + 100·completions − 200·INT) / attempts`.

One consequence worth knowing: the log only starts from the first run. If you
deploy mid-season, backfill it by pulling `/games/players` from CFBD for the
earlier weeks, or accept that totals begin the day you switch it on.

## Where the numbers come from

**ESPN** (`site.api.espn.com`) drives every run: live game state, quarter,
clock, score, and the box score line. Free, no key, and fast enough to poll
hourly. It's a public but undocumented API — if the board goes blank on a
Saturday, this is the first thing to check.

**CollegeFootballData** runs once a day, and now only for EPA per play —
everything else comes from the game log. Splitting it this way keeps you around
300 calls a month instead of 1,400.

**Google News RSS**, one query per quarterback. Stories are scored on source
tier × signal words (injury, benched, portal, draft) × recency, deduped by
headline, and cut off below a threshold you can tune at the bottom of
`fetch_data.py`. Headline and link only — no article text is reproduced.

**Kalshi** (`api.elections.kalshi.com`), three events, public and
unauthenticated — no key needed. Pulls `last_price_dollars` per contract as
the displayed percentage, keeps the top 8 candidates per market, and buckets
the rest into a "Field" row. Kalshi's per-candidate contracts don't have to
sum to exactly 100% (independent markets, some overround), so the Field
percentage is floored at 0 rather than going negative.

## Verify before you trust it

I couldn't reach ESPN or CFBD from where this was written, so the request code
is unrun. Two specific things to check on the first live run:

- **CFBD v2 parameter names.** `/ppa/players/season` is the right endpoint, but
  confirm `averagePPA.all` and the `excludeGarbageTime` parameter against the
  Swagger docs at https://api.collegefootballdata.com/docs — v2 renamed things
  from v1. If EPA comes back empty, everything else still works.
- **ESPN name matching.** `espn_names` in `fetch_data.py` matches schools by
  display name. If a QB's row shows "No game scheduled" on a day his team
  plays, the string is wrong — print `t.get("displayName")` from the scoreboard
  and fix the alias.

## What it tracks, and why

Per game: completions/attempts, yards, TD-INT, yards per attempt, completion
percentage, rushing. Season: totals plus EPA per play.

Yards per attempt and EPA sit next to the counting stats on purpose. Raw
passing yardage is the least useful number for the question this page is
actually asking — Mestemaker led the nation in yards last season in a Group of
Five offense, which is a different thing from being the answer at 1 Browns Way.
If you want to go further, opponent-adjusted splits and performance against
ranked teams are the next things worth adding.

## Roster notes

Three of the ten changed schools in the 2026 offseason: Mensah (Duke → Miami),
Leavitt (Arizona State → LSU), Mestemaker (North Texas → Oklahoma State).

Chambliss, Fifita and Maiava are in their final year of eligibility, so they're
locked into the 2027 draft. The other seven can return to school again, which
is the real risk to this list — expect at least a couple to fall off it in
December.

## Design

Redesigned as a draft-night "big board": a pinned, ranked grid of all ten
quarterbacks sits atop a banner image, with everything else (live status,
season totals, market odds, news, further reading) living behind tabs instead
of a long scroll. Board order is live — driven by Kalshi's own first-pick
odds where the market has an opinion. Full rationale and tokens are recorded
in [DESIGN.md](DESIGN.md); the short version: ground `#1B0F00`, seal brown
`#311D00`, board tan-brown `#3A2A16`, Browns orange `#FF3C00` as the only
accent, white and tan text. Headings are set in Oswald — a condensed gothic in
the same family as the Alternate Gothic / Trade Gothic Bold Condensed
lettering the classic Browns marks were built on, standing in for the team's
proprietary, non-licensable wordmark typeface. Data is set in IBM Plex Sans
with tabular figures so columns don't jitter between refreshes; ranks and odds
use IBM Plex Mono. Team logos/marks are used on the board and cards; the
banner artwork is AI-generated and user-supplied, not an official team asset.
