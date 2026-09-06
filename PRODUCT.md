# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary user is the site's owner, checking it themselves — not built for a public audience. Checked most intensively on Saturdays (noon ET through 3am ET Sunday) when games are live, and more casually during the week for season totals and news. The job: get a fast, honest read on which of ten tracked college quarterbacks is trending toward being Cleveland's answer at quarterback, without having to piece it together from box scores and team-by-team recaps.

## Product Purpose

Tracks ten college quarterbacks who could plausibly be in the 2027 NFL draft conversation, plus the news that actually matters about them, so the owner can see at a glance who's playing now, how the season is shaping up, and what's being reported — without the page ever claiming to be more current than it is.

## Positioning

Season totals are accumulated from a per-game log keyed on ESPN's event id (not pulled as season aggregates), so a bad API response can't wipe out weeks of history and a week-by-week log falls out for free. EPA per play and yards per attempt are surfaced next to raw yardage on purpose, because raw passing yards conflate quality with a team's pass volume — the page is asking a narrower question than "who put up the best national numbers," namely who's the answer at 1 Browns Way.

## Operating Context

- Data refreshes via a GitHub Actions cron: hourly Saturday noon ET–3am ET Sunday, three times a day otherwise. GitHub's scheduler is best-effort (can be delayed or skipped under load) and auto-disables after 60 days with no repo activity.
- Deployed as a static GitHub Pages site (`main`, root) — no build step; `index.html` reads `data.json` directly.
- The page displays how stale its data actually is rather than asserting it's current.

## Capabilities and Constraints

- Static HTML/CSS/JS, zero build step, no framework — this is a fixed constraint, not an early-stage default.
- Data sources: ESPN's undocumented public API (live state, quarter/clock/score, box scores), CollegeFootballData (EPA per play only, ~300 calls/month, needs a paid Patreon tier to sustain hourly Saturday polling), Google News RSS (headline + link only per story — no article text reproduced).
- Passer rating uses the NCAA formula: `(8.4·yards + 330·TD + 100·completions − 200·INT) / attempts`, not the NFL formula.
- The ten tracked quarterbacks are a fixed, manually maintained roster, not auto-discovered; expect roster churn (transfers, players exhausting eligibility) to require manual updates.
- As of the README's writing, the ESPN/CFBD request code was unverified against live traffic — CFBD v2 parameter names (`averagePPA.all`, `excludeGarbageTime`) and ESPN school-name matching (`espn_names` aliases) are the first things to check if data looks wrong.

## Brand Commitments

- Palette: seal brown `#311D00`, Browns orange `#FF3C00`, white. The masthead rule echoes the helmet's center stripe.
- Headings in Oswald (a condensed gothic standing in for the Browns' proprietary, non-licensable wordmark typeface); data in IBM Plex Sans with tabular figures so columns don't jitter on refresh.
- Team logos/marks are permitted. (The README currently states "no team marks are used" — the owner has confirmed that restriction no longer applies; the README text is stale, not a binding constraint.)

## Evidence on Hand

- `data.json`'s current snapshot is a placeholder until the first real scheduled run.
- No user testimonials, benchmarks, or third-party proof exist or should be implied — this is a personal tracking tool, not a product with an audience to persuade.
- `1000779067-CLEVELAND-Logoslick.pdf` — official Cleveland Browns 2024 NFL brand-asset sheet (16 pp.), added for future UI iterations: primary helmet mark (full color/B&W/grayscale/one-color), wordmark/logotype, exact color specs (Pantone/CMYK/RGB/hex/textile), and uniform/player-silhouette pages. Page 1 states these are NFL/Cleveland Browns trademarks provided as a licensee color/grayscale reference, not general-reproduction assets — worth keeping in mind when future work pulls marks from it. Confirmed brand color (per Users/Brand Commitments) team logos/marks are permitted for this project.

## Product Principles

1. Never claim currency the data doesn't have — show staleness honestly instead of masking it.
2. Prefer the stats that answer "who's the answer at 1 Browns Way" over stats that just look impressive nationally (EPA/YPA alongside, not instead of, raw counting stats).
3. Season totals must survive partial or bad API responses — derive them from a durable per-game log, never from a re-pulled season aggregate.
4. Stay a zero-build static page: no framework, no build tooling, `index.html` reads `data.json` directly.
5. Optimize for the owner's own fast read, not for onboarding a stranger — this is a personal tool, not a public product.

## Accessibility & Inclusion

None specified — no formal accessibility standard required.
