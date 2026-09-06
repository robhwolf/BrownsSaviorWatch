# Cleveland Browns Savior Watch

A static page tracking ten college quarterbacks who could plausibly be in the
2027 draft conversation, plus the news that actually matters about them.

```
index.html      the dashboard (reads data.json, no build step)
fetch_data.py   pulls the data, writes data.json
data.json       current snapshot — placeholder until the first real run
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

## The four sections

1. **On the field now** — only the quarterbacks currently playing, with quarter,
   clock, score and a live stat line. When nobody's playing it collapses to a
   single line naming the next kickoff.
2. **This week** — everyone else. Finals first, then whoever hasn't kicked off.
3. **Season to date** — cumulative totals, sortable by passer rating, yards,
   total touchdowns, yards per attempt, completion percentage, EPA per play, or
   fewest interceptions. Whoever leads the current sort is highlighted.
4. **What's being reported** — the ranked news list.

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

Seal brown `#311D00`, Browns orange `#FF3C00`, white. The masthead rule is the
helmet's center stripe. The team's wordmark uses a proprietary custom typeface
that isn't licensable, so headings use Oswald — a condensed gothic in the same
family as the Alternate Gothic / Trade Gothic Bold Condensed lettering the
classic Browns marks were built on. Data is set in IBM Plex Sans with tabular
figures so columns don't jitter between refreshes. No team marks are used.
