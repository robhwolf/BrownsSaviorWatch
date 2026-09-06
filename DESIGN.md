---
name: Cleveland Browns Savior Watch
description: A pinned draft-night big board for ten 2027 QB prospects, built from official Browns colors.
colors:
  ground: "#1B0F00"
  panel: "#311D00"
  board: "#3A2A16"
  edge: "#4B2E0A"
  accent: "#FF3C00"
  paper: "#FFFFFF"
  tan: "#C4AE95"
  stripe: "#FFF6EF"
typography:
  display:
    fontFamily: "Oswald, sans-serif"
    fontWeight: 600
    letterSpacing: "0.01em"
  body:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "15px"
    lineHeight: 1.5
  data:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "11px"
    letterSpacing: "0.06em"
rounded:
  sm: "2px"
  md: "3px"
  lg: "4px"
spacing:
  sm: "8px"
  md: "14px"
  lg: "22px"
components:
  plate:
    backgroundColor: "{colors.board}"
    textColor: "{colors.paper}"
    rounded: "{rounded.lg}"
    padding: "17px 10px 12px"
  tab-active:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.paper}"
    rounded: "4px 4px 0 0"
    padding: "10px 14px 8px"
---

# Design System: Cleveland Browns Savior Watch

## Overview

**Creative North Star: "The War Room Big Board"**

The page is not decorated like a draft big board — it is one. Ten quarterback
nameplates sit pinned in rank order at the top, each a small physical object
(a corner pushpin, an offset shadow) rather than a flat UI card. Everything
else the site tracks — live scores, season totals, market odds, news,
reference links — lives one tab-click away, like folders pulled off the same
war-room table rather than a long scroll of sections.

The system is confirmed dark by brief: ground #1B0F00 under warm corkboard
browns, with Browns orange reserved almost entirely for what's actually live
or leading. Nothing here is decorative chrome — a pin means a game is live, a
percentage on a nameplate is a real number pulled from Kalshi, not a design
flourish.

**Key Characteristics:**
- One accent color (orange), spent only on live state, leaders, and primary links.
- Physical, pinned-object metaphor over flat card chrome — pushpins, not colored bars.
- Tabs, not endless scroll, for anything past the at-a-glance board.
- Real data or nothing: no placeholder numbers, no invented percentages.

## Colors

Warm, near-black corkboard browns with a single hot accent; no gradients anywhere.

### Primary
- **Browns Orange** (#FF3C00): the one accent. Live-game pins and chips, season
  leaderboard highlights, tracked names in market odds, link hover, focus rings.

### Neutral
- **Ground Brown** (#1B0F00): page background. The pinned, official value —
  never substitute a different dark.
- **Panel Seal** (#311D00): card backgrounds for quarterback cards and market panels.
- **Board Tan-Brown** (#3A2A16): the big-board nameplate tiles — one step lighter
  than panel seal so the board reads as its own surface.
- **Edge Brown** (#4B2E0A): all hairline borders, dividers, and the idle (non-live) pin color.
- **Warm White** (#FFFFFF): primary text.
- **Tan** (#C4AE95): secondary text — labels, captions, school names, timestamps.
- **Stripe White** (#FFF6EF): the helmet-stripe center band only.

### Named Rules
**The One Voice Rule.** Orange marks exactly one thing at a time: live, leading,
or actionable. It never appears as passive decoration on an idle element.

## Typography

**Display Font:** Oswald (with sans-serif fallback)
**Body Font:** IBM Plex Sans (with system-ui, sans-serif fallback)
**Label/Mono Font:** IBM Plex Mono (with monospace fallback)

**Character:** A condensed, gothic display face (standing in for the Browns'
non-licensable proprietary wordmark) paired with a plain, highly legible sans
for data-dense reading, and a monospace face reserved for anything that is
actually a measurement — ranks, odds percentages, live clocks.

### Hierarchy
- **Display** (700, `clamp(28px,7.5vw,50px)`, 0.95 line-height): page masthead only (now carried by the banner image).
- **Headline** (600, 18–22px, uppercase): section and card-name headings (`h2.sec`-equivalent, quarterback names).
- **Title** (500, 14–16px, uppercase): nameplate names, table row names, tab labels.
- **Body** (400, 15px, 1.5 line-height): running copy, lede lines.
- **Label** (400–500, 10–12px, mono, tracked): ranks, odds percentages, timestamps, captions.

### Named Rules
**The No-Kicker Rule.** No eyebrow or kicker label ever sits above a heading.
The heading carries its own weight.

## Layout

Single centered column, `max-width: 900px`, 16px side padding. The board is a
`grid-template-columns: repeat(auto-fill, minmax(126px, 1fr))` that reflows
from five-wide on desktop to two-wide on narrow phones with no breakpoint
authored by hand. Content below the board lives in tab panels, one visible at
a time, switched without navigation. The banner is a fixed 3:1 `aspect-ratio`
image spanning the full column width — the only element in the system with a
locked ratio.

## Elevation & Depth

Flat backgrounds, lifted objects. Cards and nameplates sit on soft drop
shadows with real offset and blur (never a flat colored halo), reading as
objects resting on the dark ground rather than flush panels. Each pinned
element additionally carries a small circular "pin" with its own 2px offset
shadow, the system's one recurring depth cue.

### Shadow Vocabulary
- **plate/qb** (`box-shadow: 0 3px 9px rgba(0,0,0,.35-.45)`): the resting lift for every pinned card and nameplate.
- **pin** (`box-shadow: 0 2px 2-3px rgba(0,0,0,.4-.45)`): the small pushpin shadow, on every plate and card corner.

### Named Rules
**The Pin, Not the Bar Rule.** Status and emphasis are marked by a small
pinned dot in the corner, never by a colored `border-left`/`border-right`
stripe. This replaced the previous design's 6px rib-column accent.

## Shapes

Small, consistent corner radius (2–4px) everywhere — never sharp, never
pill-shaped. Borders are 1px hairlines in Edge Brown. The pin is the system's
only circular form; everything else is rectangular.

## Components

### Nameplate (`.plate`)
The signature component. A button styled as a pinned index card: pushpin dot
top-center, a two-digit mono rank, team logo, last name in Oswald caps, school
in tan, and — only when Kalshi's market actually has an opinion — a mono
percentage line. Clicking one jumps to that quarterback's full card in the
Live or This Week tab. Live quarterbacks get an orange pin; everyone else,
Edge Brown.

### Quarterback card (`.qb`)
Panel-seal background, corner pin (left edge, not top-center, to distinguish
it from a nameplate), team logo, name/school/class, a status chip, and — when
a game has been played — the six-stat line (Cmp-Att, Pass yds, TD-INT,
Yds/att, Comp %, Rush yds).

### Tabs
Folder-tab convention: inactive tabs sit on Panel Seal with a visible bottom
rule; the active tab's background becomes Ground Brown and its bottom border
disappears, so it visually merges with the panel beneath it. One small mono
badge (`.tab .n`) on the Live tab shows the live count.

### Chips (`.chip`)
- **Live:** orange fill, seal text, pulsing dot — reserved for a genuinely
  in-progress game, never decorative.
- **Final / Scheduled:** outlined, tan or white text, no animation.

### Market odds row (`.odds-row`)
Plain ranked list, name left / percentage right in mono-weight Oswald —
deliberately not a chart or progress bar. Tracked quarterbacks render bold and
orange; the field bucket renders quiet and italic.

## Do's and Don'ts

### Do:
- **Do** spend orange on exactly one thing per element: live, leading, or the primary link.
- **Do** mark status with the corner pin device, consistently, everywhere a card or nameplate needs one.
- **Do** show a real number (Kalshi odds, EPA, passer rating) or omit the field — never a placeholder value.
- **Do** keep every shadow a real offset-plus-blur; a flat colored halo is not depth.

### Don't:
- **Don't** add a colored `border-left`/`border-right` bar as an accent device; use the pin instead.
- **Don't** add a kicker/eyebrow label above any heading.
- **Don't** introduce a second display typeface; Oswald carries every heading in the system.
- **Don't** use a gradient, glass, or blur effect anywhere in this system — the ground is flat by construction.
- **Don't** set text color to Edge Brown (#4B2E0A) — it's a border/divider/idle-pin color only, ~1.3:1 against Panel Seal and Board Tan-Brown. For quieter secondary text (e.g. an empty-state line), use Tan at a reduced weight or italic, never a darker fill.
