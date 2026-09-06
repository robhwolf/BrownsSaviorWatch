#!/usr/bin/env python3
"""
Cleveland Browns Savior Watch - data fetcher.

Writes data.json, which index.html reads.

Sources:
  ESPN  - free, no key. Team identities, live game state, box scores,
          forward schedule, logos. Runs every time.
  CFBD  - keyed. EPA per play only. Runs once a day.

Teams are resolved to ESPN numeric ids once and cached in data.json, then
every game lookup matches on id rather than on a display-name string. Name
matching was too brittle - one mismatch and a quarterback silently shows
"no game scheduled" on a day his team is playing.
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
ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"

# A plain script user-agent gets refused by some edge configs. Look like a browser.
UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
}

QBS = [
    {"name": "Trinidad Chambliss", "school": "Ole Miss",       "cls": "6th yr",
     "cfbd_team": "Ole Miss",       "espn_names": ["Ole Miss", "Mississippi", "Ole Miss Rebels"]},
    {"name": "Dante Moore",        "school": "Oregon",         "cls": "RS Jr",
     "cfbd_team": "Oregon",         "espn_names": ["Oregon", "Oregon Ducks"]},
    {"name": "CJ Carr",            "school": "Notre Dame",     "cls": "RS So",
     "cfbd_team": "Notre Dame",     "espn_names": ["Notre Dame", "Notre Dame Fighting Irish"]},
    {"name": "Darian Mensah",      "school": "Miami",          "cls": "Jr",
     "cfbd_team": "Miami",          "espn_names": ["Miami", "Miami (FL)", "Miami Hurricanes"]},
    {"name": "Julian Sayin",       "school": "Ohio State",     "cls": "RS So",
     "cfbd_team": "Ohio State",     "espn_names": ["Ohio State", "Ohio State Buckeyes"]},
    {"name": "Drew Mestemaker",    "school": "Oklahoma State", "cls": "RS So",
     "cfbd_team": "Oklahoma State", "espn_names": ["Oklahoma State", "Oklahoma State Cowboys"]},
    {"name": "Arch Manning",       "school": "Texas",          "cls": "RS Jr",
     "cfbd_team": "Texas",          "espn_names": ["Texas", "Texas Longhorns"]},
    {"name": "Sam Leavitt",        "school": "LSU",            "cls": "RS Jr",
     "cfbd_team": "LSU",            "espn_names": ["LSU", "LSU Tigers"]},
    {"name": "Jayden Maiava",      "school": "USC",            "cls": "RS Sr",
     "cfbd_team": "USC",            "espn_names": ["USC", "Southern California", "USC Trojans"]},
    {"name": "Noah Fifita",        "school": "Arizona",        "cls": "RS Sr",
     "cfbd_team": "Arizona",        "espn_names": ["Arizona", "Arizona Wildcats"]},
]

SOURCE_TIER = {
    "espn.com": 5, "theathletic.com": 5, "nytimes.com": 5, "si.com": 4,
    "cbssports.com": 4, "foxsports.com": 4, "yahoo.com": 3, "247sports.com": 4,
    "on3.com": 4, "rivals.com": 3, "usatoday.com": 3, "athlonsports.com": 2,
    "clutchpoints.com": 1, "sportskeeda.com": 1, "msn.com": 1,
}
HIGH_SIGNAL = [
    ("injur", 6), ("out for", 6), ("surgery", 6), ("concussion", 6),
    ("benched", 6), ("suspend", 5), ("transfer portal", 5), ("questionable", 4),
    ("draft", 3), ("heisman", 3), ("record", 2), ("nfl", 2),
]
NEWS_FLOOR = 16      # raise to see less, lower to see more
NEWS_MAX = 8

DIAG = {"errors": [], "notes": []}


def get_json(url, headers=None, tries=3, label=""):
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
                msg = f"{label or url[:70]}: {e}"
                print(f"  ! {msg}", file=sys.stderr)
                DIAG["errors"].append(msg)
                return None
            time.sleep(2 * (i + 1))


def get_text(url, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(2)


# ---------------------------------------------------------------------------
# Team identity: resolve once, cache forever
# ---------------------------------------------------------------------------

def pick_logo(team):
    """Prefer ESPN's dark-background variant - the default marks vanish on brown."""
    logos = team.get("logos") or []
    for lg in logos:
        if "dark" in (lg.get("rel") or []):
            return lg.get("href")
    if logos:
        return logos[0].get("href")
    return team.get("logo")


def resolve_teams(prev):
    """Map each school to its ESPN team id, logo and colour."""
    teams = dict(prev or {})
    missing = [q for q in QBS if q["school"] not in teams]
    if not missing:
        return teams

    data = get_json(f"{ESPN}/teams?limit=1000", label="ESPN teams list")
    if not data:
        return teams
    try:
        entries = data["sports"][0]["leagues"][0]["teams"]
    except (KeyError, IndexError):
        DIAG["errors"].append("ESPN teams list: unexpected shape")
        return teams

    index = {}
    for e in entries:
        t = e.get("team") or {}
        for key in (t.get("displayName"), t.get("shortDisplayName"),
                    t.get("location"), t.get("nickname"), t.get("name")):
            if key:
                index.setdefault(key.lower(), t)

    for q in missing:
        hit = next((index[n.lower()] for n in q["espn_names"] if n.lower() in index), None)
        if not hit:
            DIAG["errors"].append(f"could not resolve {q['school']} to an ESPN team")
            continue
        teams[q["school"]] = {
            "id": str(hit.get("id")),
            "abbr": hit.get("abbreviation"),
            "display": hit.get("displayName"),
            "logo": pick_logo(hit),
            "color": "#" + (hit.get("color") or "444444").lstrip("#"),
        }
    return teams


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------

def scoreboard(days_back=3, days_fwd=2):
    events = []
    today = datetime.now(timezone.utc).date()
    for off in range(-days_back, days_fwd + 1):
        d = (today + timedelta(days=off)).strftime("%Y%m%d")
        data = get_json(f"{ESPN}/scoreboard?groups=80&limit=400&dates={d}",
                        label=f"scoreboard {d}")
        if data and data.get("events"):
            events.extend(data["events"])
    return events


def team_side(event, team_id):
    comp = (event.get("competitions") or [{}])[0]
    for c in comp.get("competitors", []):
        if str((c.get("team") or {}).get("id")) == str(team_id):
            return c, comp
    return None, None


def find_game(events, team_id):
    live = final = upcoming = None
    for ev in events:
        me, _ = team_side(ev, team_id)
        if not me:
            continue
        state = ((ev.get("status") or {}).get("type") or {}).get("state")
        if state == "in":
            live = live or ev
        elif state == "post":
            if final is None or ev.get("date", "") > final.get("date", ""):
                final = ev
        elif upcoming is None:
            upcoming = ev
    return live or final or upcoming


def describe(ev, team_id):
    if not ev:
        return {"state": "idle", "label": "No game found"}
    me, comp = team_side(ev, team_id)
    opp = next((c for c in comp.get("competitors", []) if c is not me), {})
    ot = opp.get("team") or {}
    status = ev.get("status") or {}
    state = (status.get("type") or {}).get("state")
    rank = (opp.get("curatedRank") or {}).get("current")
    ha = "vs" if me.get("homeAway") == "home" else "at"
    out = {
        "event_id": str(ev.get("id")),
        "opponent": ot.get("shortDisplayName") or ot.get("displayName") or "TBD",
        "opponent_logo": pick_logo(ot),
        "opponent_rank": rank if rank and rank < 26 else None,
        "home_away": ha,
        "kickoff": ev.get("date"),
        "broadcast": next((b.get("names", [None])[0]
                           for b in (comp.get("broadcasts") or []) if b.get("names")), None),
    }
    if state == "in":
        out.update({"state": "live", "clock": status.get("displayClock"),
                    "period": status.get("period"),
                    "score": f"{me.get('score','0')}-{opp.get('score','0')}",
                    "label": f"{ha} {out['opponent']}"})
    elif state == "post":
        res = "W" if me.get("winner") is True else ("L" if opp.get("winner") is True else "T")
        out.update({"state": "final", "result": res,
                    "score": f"{me.get('score','0')}-{opp.get('score','0')}",
                    "label": f"{res} {me.get('score','0')}-{opp.get('score','0')} {ha} {out['opponent']}"})
    else:
        out.update({"state": "scheduled", "label": f"{ha} {out['opponent']}"})
    return out


def next_game(team_id, team_name):
    """First future game on the team's own schedule - reaches past the scoreboard window."""
    data = get_json(f"{ESPN}/teams/{team_id}/schedule?season={SEASON}",
                    label=f"schedule {team_name}")
    if not data:
        return None
    now = datetime.now(timezone.utc)
    best = None
    for ev in data.get("events") or []:
        try:
            when = datetime.fromisoformat((ev.get("date") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        state = ((ev.get("status") or {}).get("type") or {}).get("state")
        if state == "post" or when <= now:
            continue
        if best is None or when < best[0]:
            best = (when, ev)
    if not best:
        return None
    info = describe(best[1], team_id)
    return {k: info.get(k) for k in
            ("opponent", "opponent_logo", "opponent_rank", "home_away", "kickoff",
             "broadcast", "label")}


def box_line(event_id, player_name):
    if not event_id:
        return None
    data = get_json(f"{ESPN}/summary?event={event_id}", label=f"box {event_id}")
    if not data:
        return None
    line, last = {}, player_name.split()[-1].lower()
    for team in (data.get("boxscore") or {}).get("players", []):
        for cat in team.get("statistics", []):
            keys = [k.lower() for k in cat.get("keys", [])]
            for ath in cat.get("athletes", []):
                if last not in (ath.get("athlete") or {}).get("displayName", "").lower():
                    continue
                row = dict(zip(keys, ath.get("stats", [])))
                if cat.get("name") == "passing":
                    cmp_, att = (row.get("c/att", "0/0").split("/") + ["0"])[:2]
                    line.update({"cmp": int(cmp_ or 0), "att": int(att or 0),
                                 "pass_yds": int(row.get("yds", 0) or 0),
                                 "pass_td": int(row.get("td", 0) or 0),
                                 "int": int(row.get("int", 0) or 0)})
                elif cat.get("name") == "rushing":
                    line.update({"rush_att": int(row.get("car", 0) or 0),
                                 "rush_yds": int(row.get("yds", 0) or 0),
                                 "rush_td": int(row.get("td", 0) or 0)})
    if line.get("att"):
        line["comp_pct"] = round(100 * line["cmp"] / line["att"], 1)
        line["ypa"] = round(line["pass_yds"] / line["att"], 1)
    return line or None


# ---------------------------------------------------------------------------
# Season accumulation
# ---------------------------------------------------------------------------

def clean_log(log):
    """Drop anything without a real ESPN event id - purges seeded placeholder rows."""
    return [g for g in (log or []) if str(g.get("event_id", "")).isdigit()]


def merge_log(prev_log, status, line):
    log = clean_log(prev_log)
    if status.get("state") != "final" or not line or not line.get("att"):
        return log
    entry = dict(line)
    entry.update({k: status.get(k) for k in
                  ("event_id", "opponent", "home_away", "result", "score")})
    entry["date"] = status.get("kickoff")
    for i, e in enumerate(log):
        if e.get("event_id") == entry["event_id"]:
            log[i] = entry
            return log
    log.append(entry)
    log.sort(key=lambda e: e.get("date") or "")
    return log


def season_from_log(log, epa=None):
    if not log:
        return {"games": 0, "epa_per_play": epa}
    t = {k: sum(int(g.get(k) or 0) for g in log) for k in
         ("cmp", "att", "pass_yds", "pass_td", "int", "rush_att", "rush_yds", "rush_td")}
    att = t["att"] or 1
    rating = ((8.4 * t["pass_yds"]) + (330 * t["pass_td"])
              + (100 * t["cmp"]) - (200 * t["int"])) / att
    wins = sum(1 for g in log if g.get("result") == "W")
    return {
        "games": len(log), "record": f"{wins}-{len(log) - wins}",
        "cmp": t["cmp"], "att": t["att"],
        "comp_pct": round(100 * t["cmp"] / att, 1),
        "pass_yds": t["pass_yds"], "ypa": round(t["pass_yds"] / att, 1),
        "pass_td": t["pass_td"], "int": t["int"],
        "td_int": f"{t['pass_td']}-{t['int']}",
        "rush_yds": t["rush_yds"], "rush_td": t["rush_td"],
        "total_td": t["pass_td"] + t["rush_td"],
        "ypg": round(t["pass_yds"] / len(log)),
        "rating": round(rating, 1), "epa_per_play": epa,
    }


def cfbd_epa(qb):
    if not CFBD_KEY:
        return None
    q = urllib.parse.urlencode({"year": SEASON, "team": qb["cfbd_team"],
                                "excludeGarbageTime": "true"})
    rows = get_json(f"{CFBD_BASE}/ppa/players/season?{q}",
                    headers={"Authorization": f"Bearer {CFBD_KEY}"},
                    label=f"CFBD ppa {qb['cfbd_team']}")
    for r in rows or []:
        if qb["name"].split()[-1].lower() in (r.get("name") or "").lower():
            v = (r.get("averagePPA") or {}).get("all")
            if v is not None:
                return round(v, 3)
    return None


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def news_for(qb):
    q = urllib.parse.quote(f'"{qb["name"]}" {qb["school"]} football')
    xml = get_text(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")
    if not xml:
        return []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    for it in root.iter("item"):
        src_el = it.find("source")
        domain = ""
        if src_el is not None:
            domain = re.sub(r"^https?://(www\.)?", "", src_el.get("url", "")).split("/")[0]
        out.append({
            "headline": (it.findtext("title") or "").strip().rsplit(" - ", 1)[0],
            "source": (src_el.text if src_el is not None else "") or domain,
            "domain": domain, "url": (it.findtext("link") or "").strip(),
            "published": (it.findtext("pubDate") or "").strip(), "player": qb["name"],
        })
    return out[:12]


def score_news(item):
    s = SOURCE_TIER.get(item["domain"], 1) * 2
    head = item["headline"].lower()
    for word, weight in HIGH_SIGNAL:
        if word in head:
            s += weight
    try:
        pub = datetime.strptime(item["published"], "%a, %d %b %Y %H:%M:%S %Z") \
            .replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - pub).total_seconds() / 3600
        s += 7 if age < 24 else 3 if age < 72 else 0
        item["age_hours"] = round(age)
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
            if item["score"] >= NEWS_FLOOR:
                out.append(item)
    out.sort(key=lambda x: -x["score"])
    return out[:NEWS_MAX]


# ---------------------------------------------------------------------------

def main():
    now = datetime.now(timezone.utc)
    print(f"Fetching {now.isoformat()}")

    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT))
        except Exception:
            pass
    prev_qb = {q["name"]: q for q in prev.get("quarterbacks", [])}

    teams = resolve_teams(prev.get("teams"))
    print(f"  teams resolved: {len(teams)}/{len(QBS)}")

    events = scoreboard()
    print(f"  {len(events)} FBS events in window")
    if not events:
        DIAG["errors"].append("scoreboard returned no events at all")

    run_daily = (os.environ.get("FORCE_DAILY") == "1" or now.hour == 12 or not prev_qb)

    rows, matched = [], 0
    for qb in QBS:
        team = teams.get(qb["school"])
        old = prev_qb.get(qb["name"], {})
        if not team:
            rows.append({"name": qb["name"], "school": qb["school"], "class": qb["cls"],
                         "team": None, "status": {"state": "idle", "label": "Team unresolved"},
                         "game": None, "next_game": None,
                         "log": clean_log(old.get("log")),
                         "season": season_from_log(clean_log(old.get("log")))})
            continue

        status = describe(find_game(events, team["id"]), team["id"])
        if status["state"] != "idle":
            matched += 1
        line = box_line(status.get("event_id"), qb["name"]) \
            if status["state"] in ("live", "final") else None

        nxt = old.get("next_game")
        stale = run_daily or not nxt or (nxt.get("kickoff") or "") < now.isoformat()
        if status["state"] == "live":
            nxt = nxt  # don't burn a call mid-game
        elif stale:
            nxt = next_game(team["id"], qb["school"])

        log = merge_log(old.get("log"), status, line)
        epa = cfbd_epa(qb) if run_daily else (old.get("season") or {}).get("epa_per_play")

        print(f"  {qb['name']:<20} {status['state']:<10} {status.get('label','')}")
        rows.append({"name": qb["name"], "school": qb["school"], "class": qb["cls"],
                     "team": team, "status": status, "game": line, "next_game": nxt,
                     "log": log, "season": season_from_log(log, epa)})

    payload = {
        "updated_at": now.isoformat(), "season": SEASON,
        "live_count": sum(1 for r in rows if r["status"]["state"] == "live"),
        "teams": teams, "quarterbacks": rows, "news": build_news(),
        "diagnostics": {**DIAG, "events_seen": len(events),
                        "games_matched": matched, "teams_resolved": len(teams)},
    }
    json.dump(payload, open(OUT, "w"), indent=2)
    logged = sum(len(r["log"]) for r in rows)
    print(f"Wrote {OUT} - {matched}/{len(QBS)} matched to a game, "
          f"{logged} games logged, {len(payload['news'])} news items")
    if DIAG["errors"]:
        print("Problems:")
        for e in DIAG["errors"][:12]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
