#!/usr/bin/env python3
"""
Cleveland Browns Savior Watch - data fetcher.

Writes data.json, which index.html reads. Run it on a schedule
(see .github/workflows/update.yml).

Two sources, deliberately split by cost:
  ESPN  - free, no key, live game state + box scores. Runs every time.
  CFBD  - keyed, advanced metrics (EPA/success rate). Runs once a day
          unless FORCE_CFBD=1, to stay far under the call quota.

ESPN's endpoints are public but undocumented. They can change without
notice. If the page goes stale, check ESPN first.
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

SEASON = 2026
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

CFBD_KEY = os.environ.get("CFBD_API_KEY", "").strip()
CFBD_BASE = "https://api.collegefootballdata.com"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"

UA = {"User-Agent": "browns-savior-watch/1.0"}

# ---------------------------------------------------------------------------
# The watch list. `espn_names` are the strings ESPN uses for the school in its
# scoreboard feed - matching on name avoids hardcoding team IDs that drift.
# `cfbd_team` must match CFBD's team name exactly.
# ---------------------------------------------------------------------------
QBS = [
    {"name": "Trinidad Chambliss", "school": "Ole Miss",       "cls": "6th yr",
     "cfbd_team": "Ole Miss",       "espn_names": ["Ole Miss", "Mississippi"]},
    {"name": "Dante Moore",        "school": "Oregon",         "cls": "RS Jr",
     "cfbd_team": "Oregon",         "espn_names": ["Oregon"]},
    {"name": "CJ Carr",            "school": "Notre Dame",     "cls": "RS So",
     "cfbd_team": "Notre Dame",     "espn_names": ["Notre Dame"]},
    {"name": "Darian Mensah",      "school": "Miami",          "cls": "Jr",
     "cfbd_team": "Miami",          "espn_names": ["Miami", "Miami (FL)"]},
    {"name": "Julian Sayin",       "school": "Ohio State",     "cls": "RS So",
     "cfbd_team": "Ohio State",     "espn_names": ["Ohio State"]},
    {"name": "Drew Mestemaker",    "school": "Oklahoma State", "cls": "RS So",
     "cfbd_team": "Oklahoma State", "espn_names": ["Oklahoma State"]},
    {"name": "Arch Manning",       "school": "Texas",          "cls": "RS Jr",
     "cfbd_team": "Texas",          "espn_names": ["Texas"]},
    {"name": "Sam Leavitt",        "school": "LSU",            "cls": "RS Jr",
     "cfbd_team": "LSU",            "espn_names": ["LSU"]},
    {"name": "Jayden Maiava",      "school": "USC",            "cls": "RS Sr",
     "cfbd_team": "USC",            "espn_names": ["USC", "Southern California"]},
    {"name": "Noah Fifita",        "school": "Arizona",        "cls": "RS Sr",
     "cfbd_team": "Arizona",        "espn_names": ["Arizona"]},
]

# News source weighting. Higher = more trusted. Anything unlisted scores 1.
SOURCE_TIER = {
    "espn.com": 5, "theathletic.com": 5, "nytimes.com": 5, "si.com": 4,
    "cbssports.com": 4, "foxsports.com": 4, "yahoo.com": 3, "247sports.com": 4,
    "on3.com": 4, "rivals.com": 3, "usatoday.com": 3, "athlonsports.com": 2,
    "clutchpoints.com": 1, "sportskeeda.com": 1, "msn.com": 1,
}

# Words that make a story matter rather than just exist.
HIGH_SIGNAL = [
    ("injur", 5), ("out for", 5), ("surgery", 5), ("concussion", 5),
    ("benched", 5), ("suspend", 4), ("transfer portal", 4), ("questionable", 3),
    ("draft", 3), ("nfl", 2), ("record", 2), ("heisman", 2), ("start", 1),
]


def get_json(url, headers=None, tries=3):
    h = dict(UA)
    if headers:
        h.update(headers)
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == tries - 1:
                print(f"  ! {url[:80]} failed: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))


def get_text(url, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if i == tries - 1:
                print(f"  ! {url[:80]} failed: {e}", file=sys.stderr)
                return None
            time.sleep(2)


# ---------------------------------------------------------------------------
# ESPN: game state + box score
# ---------------------------------------------------------------------------

def espn_scoreboard(days_back=2, days_fwd=8):
    """Pull scoreboards around today so we catch live, final and upcoming games."""
    events = []
    today = datetime.now(timezone.utc).date()
    for offset in range(-days_back, days_fwd + 1):
        d = (today + timedelta(days=offset)).strftime("%Y%m%d")
        # groups=80 is all of FBS. limit is generous because Saturdays are busy.
        data = get_json(f"{ESPN_BASE}/scoreboard?groups=80&limit=400&dates={d}")
        if data and data.get("events"):
            events.extend(data["events"])
    return events


def find_game(events, espn_names):
    """Return (event, is_home) for the most relevant game for a school."""
    live = final = upcoming = None
    for ev in events:
        comp = (ev.get("competitions") or [{}])[0]
        for c in comp.get("competitors", []):
            t = c.get("team", {})
            names = {t.get("displayName"), t.get("shortDisplayName"),
                     t.get("location"), t.get("name")}
            if names & set(espn_names):
                state = ((ev.get("status") or {}).get("type") or {}).get("state")
                if state == "in":
                    live = live or (ev, c)
                elif state == "post":
                    if final is None or ev.get("date", "") > final[0].get("date", ""):
                        final = (ev, c)
                elif upcoming is None:
                    upcoming = (ev, c)
    return live or final or upcoming


def game_status(match):
    """Flatten an ESPN event into the shape the page renders."""
    if not match:
        return {"state": "idle", "label": "No game scheduled"}
    ev, me = match
    comp = (ev.get("competitions") or [{}])[0]
    status = ev.get("status") or {}
    stype = status.get("type") or {}
    state = stype.get("state")
    opp = next((c for c in comp.get("competitors", []) if c is not me), {})
    opp_name = (opp.get("team") or {}).get("shortDisplayName", "TBD")
    opp_rank = opp.get("curatedRank", {}).get("current")
    home_away = "vs" if me.get("homeAway") == "home" else "at"

    out = {
        "event_id": ev.get("id"),
        "opponent": opp_name,
        "opponent_rank": opp_rank if opp_rank and opp_rank < 26 else None,
        "home_away": home_away,
        "kickoff": ev.get("date"),
    }
    if state == "in":
        out["state"] = "live"
        out["clock"] = status.get("displayClock")
        out["period"] = status.get("period")
        out["label"] = f"{home_away} {opp_name}"
        out["score"] = f"{me.get('score','0')}-{opp.get('score','0')}"
    elif state == "post":
        out["state"] = "final"
        won = me.get("winner") is True
        out["result"] = "W" if won else ("L" if opp.get("winner") is True else "T")
        out["score"] = f"{me.get('score','0')}-{opp.get('score','0')}"
        out["label"] = f"{out['result']} {out['score']} {home_away} {opp_name}"
    else:
        out["state"] = "scheduled"
        out["label"] = f"{home_away} {opp_name}"
    return out


def espn_box(event_id, player_name):
    """Passing and rushing line for one player out of a game summary."""
    if not event_id:
        return None
    data = get_json(f"{ESPN_BASE}/summary?event={event_id}")
    if not data:
        return None
    line = {}
    last = player_name.split()[-1].lower()
    for team in (data.get("boxscore") or {}).get("players", []):
        for cat in team.get("statistics", []):
            keys = [k.lower() for k in cat.get("keys", [])]
            for ath in cat.get("athletes", []):
                nm = (ath.get("athlete") or {}).get("displayName", "").lower()
                if last not in nm:
                    continue
                vals = ath.get("stats", [])
                row = dict(zip(keys, vals))
                if cat.get("name") == "passing":
                    ca = row.get("c/att", "0/0")
                    cmp_, att = (ca.split("/") + ["0"])[:2]
                    line.update({
                        "cmp": int(cmp_ or 0), "att": int(att or 0),
                        "pass_yds": int(row.get("yds", 0) or 0),
                        "pass_td": int(row.get("td", 0) or 0),
                        "int": int(row.get("int", 0) or 0),
                        "sacks": (row.get("sacks-sackyardslost") or "0-0").split("-")[0],
                    })
                elif cat.get("name") == "rushing":
                    line.update({
                        "rush_att": int(row.get("car", 0) or 0),
                        "rush_yds": int(row.get("yds", 0) or 0),
                        "rush_td": int(row.get("td", 0) or 0),
                    })
    if line.get("att"):
        line["comp_pct"] = round(100 * line["cmp"] / line["att"], 1)
        line["ypa"] = round(line["pass_yds"] / line["att"], 1)
    return line or None


# ---------------------------------------------------------------------------
# CFBD: season totals + advanced metrics
# ---------------------------------------------------------------------------

def cfbd(path, **params):
    if not CFBD_KEY:
        return None
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return get_json(f"{CFBD_BASE}{path}?{q}",
                    headers={"Authorization": f"Bearer {CFBD_KEY}"})


def cfbd_epa(qb):
    """EPA per play for the season. Everything else is totalled from the game log."""
    ppa = cfbd("/ppa/players/season", year=SEASON, team=qb["cfbd_team"],
               excludeGarbageTime="true")
    if not ppa:
        return None
    for r in ppa:
        if qb["name"].split()[-1].lower() in (r.get("name") or "").lower():
            allp = r.get("averagePPA") or {}
            if allp.get("all") is not None:
                return round(allp["all"], 3)
    return None


# ---------------------------------------------------------------------------
# Season accumulation
#
# Totals are built from a stored game log rather than pulled as season stats.
# That way a bad CFBD response can't wipe out weeks of history, and you get a
# week-by-week log for free.
# ---------------------------------------------------------------------------

def merge_log(prev_log, status, line):
    """Add or update this week's entry. Keyed on event id, so reruns are safe."""
    log = list(prev_log or [])
    if status.get("state") != "final" or not line or not line.get("att"):
        return log
    entry = dict(line)
    entry.update({
        "event_id": status.get("event_id"),
        "opponent": status.get("opponent"),
        "home_away": status.get("home_away"),
        "result": status.get("result"),
        "score": status.get("score"),
        "date": status.get("kickoff"),
    })
    for i, e in enumerate(log):
        if e.get("event_id") == entry["event_id"]:
            log[i] = entry
            return log
    log.append(entry)
    log.sort(key=lambda e: e.get("date") or "")
    return log


def season_from_log(log, epa=None):
    """Cumulative totals. Rating is the NCAA passer efficiency formula."""
    if not log:
        return {"games": 0, "epa_per_play": epa}
    t = {k: sum(int(g.get(k) or 0) for g in log) for k in
         ("cmp", "att", "pass_yds", "pass_td", "int", "rush_att", "rush_yds", "rush_td")}
    att = t["att"] or 1
    rating = ((8.4 * t["pass_yds"]) + (330 * t["pass_td"])
              + (100 * t["cmp"]) - (200 * t["int"])) / att
    wins = sum(1 for g in log if g.get("result") == "W")
    return {
        "games": len(log),
        "record": f"{wins}-{len(log) - wins}",
        "cmp": t["cmp"], "att": t["att"],
        "comp_pct": round(100 * t["cmp"] / att, 1),
        "pass_yds": t["pass_yds"],
        "ypa": round(t["pass_yds"] / att, 1),
        "pass_td": t["pass_td"], "int": t["int"],
        "td_int": f"{t['pass_td']}-{t['int']}",
        "rush_yds": t["rush_yds"], "rush_td": t["rush_td"],
        "total_td": t["pass_td"] + t["rush_td"],
        "ypg": round(t["pass_yds"] / len(log)),
        "rating": round(rating, 1),
        "epa_per_play": epa,
    }


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def news_for(qb):
    q = urllib.parse.quote(f'"{qb["name"]}" {qb["school"]} football')
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    xml = get_text(url)
    if not xml:
        return []
    items = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src_el = it.find("source")
        src = (src_el.text if src_el is not None else "") or ""
        domain = ""
        if src_el is not None:
            domain = re.sub(r"^https?://(www\.)?", "", src_el.get("url", "")).split("/")[0]
        items.append({
            "headline": title.rsplit(" - ", 1)[0],
            "source": src, "domain": domain, "url": link,
            "published": pub, "player": qb["name"],
        })
    return items[:12]


def score_news(item):
    """Source quality x how much the story matters x how fresh it is."""
    s = SOURCE_TIER.get(item["domain"], 1) * 2
    head = item["headline"].lower()
    for word, weight in HIGH_SIGNAL:
        if word in head:
            s += weight
    try:
        pub = datetime.strptime(item["published"], "%a, %d %b %Y %H:%M:%S %Z")
        pub = pub.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc) - pub).total_seconds() / 3600
        s += 6 if age_h < 24 else 3 if age_h < 72 else 0
        item["age_hours"] = round(age_h)
    except Exception:
        item["age_hours"] = None
    return s


def build_news():
    seen, out = set(), []
    for qb in QBS:
        for item in news_for(qb):
            key = re.sub(r"[^a-z0-9]", "", item["headline"].lower())[:60]
            if key in seen:
                continue
            seen.add(key)
            item["score"] = score_news(item)
            out.append(item)
    out.sort(key=lambda x: -x["score"])
    # Keep only stories that clear the bar. Tune the threshold to taste.
    return [i for i in out if i["score"] >= 8][:18]


# ---------------------------------------------------------------------------

def main():
    print(f"Fetching {datetime.now(timezone.utc).isoformat()}")
    events = espn_scoreboard()
    print(f"  {len(events)} FBS events in window")

    # Reuse yesterday's CFBD block unless it's the daily run.
    prev = {}
    if os.path.exists(OUT):
        try:
            with open(OUT) as f:
                prev = json.load(f)
        except Exception:
            pass
    prev_qb = {q["name"]: q for q in prev.get("quarterbacks", [])}
    run_cfbd = bool(CFBD_KEY) and (
        os.environ.get("FORCE_CFBD") == "1"
        or datetime.now(timezone.utc).hour == 12
        or not prev_qb
    )

    rows = []
    for qb in QBS:
        print(f"  {qb['name']} ({qb['school']})")
        old = prev_qb.get(qb["name"], {})
        status = game_status(find_game(events, qb["espn_names"]))
        game = None
        if status["state"] in ("live", "final"):
            game = espn_box(status.get("event_id"), qb["name"])

        log = merge_log(old.get("log"), status, game)
        epa = cfbd_epa(qb) if run_cfbd else (old.get("season") or {}).get("epa_per_play")
        rows.append({
            "name": qb["name"], "school": qb["school"], "class": qb["cls"],
            "status": status,
            "game": game,
            "log": log,
            "season": season_from_log(log, epa),
        })

    live_rows = [r for r in rows if r["status"]["state"] == "live"]
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "season": SEASON,
        "cfbd_refreshed": run_cfbd,
        "live_count": len(live_rows),
        "quarterbacks": rows,
        "news": build_news(),
    }
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)
    logged = sum(len(r["log"]) for r in rows)
    print(f"Wrote {OUT} - {len(live_rows)} live, {logged} games logged, "
          f"{len(payload['news'])} news items")


if __name__ == "__main__":
    main()
