#!/usr/bin/env python3
"""
Cleveland Browns Savior Watch - data fetcher.

Everything comes from CollegeFootballData. ESPN's endpoints return 403 to
datacenter IPs, so they can't be used from a GitHub Actions runner at all.

Calls per run:
  /teams/fbs        once, cached in data.json
  /games            1  - whole season, gives schedule + results for all ten
  /scoreboard       1  - live status (needs a Patreon tier; degrades quietly)
  /games/players    only for finished games not yet in the log
  /ppa/players/season  10, once a day
  Kalshi /events    3  - public, unauthenticated - draft pick, draft team, Heisman
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

SEASON = 2026
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
KEY = os.environ.get("CFBD_API_KEY", "").strip()
CFBD = "https://api.collegefootballdata.com"

QBS = [
    {"name": "Trinidad Chambliss", "school": "Ole Miss",       "cls": "6th yr", "espn_id": 4911529},
    {"name": "Dante Moore",        "school": "Oregon",         "cls": "RS Jr",  "espn_id": 4870921},
    {"name": "CJ Carr",            "school": "Notre Dame",     "cls": "RS So",  "espn_id": 5079369},
    {"name": "Darian Mensah",      "school": "Miami",          "cls": "Jr",     "espn_id": 5121169},
    {"name": "Julian Sayin",       "school": "Ohio State",     "cls": "RS So",  "espn_id": 5079712},
    {"name": "Drew Mestemaker",    "school": "Oklahoma State", "cls": "RS So",  "espn_id": 5219834},
    {"name": "Arch Manning",       "school": "Texas",          "cls": "RS Jr",  "espn_id": 4870906},
    {"name": "Sam Leavitt",        "school": "LSU",            "cls": "RS Jr",  "espn_id": 5078810},
    {"name": "Jayden Maiava",      "school": "USC",            "cls": "RS Sr",  "espn_id": 4685454},
    {"name": "Noah Fifita",        "school": "Arizona",        "cls": "RS Sr",  "espn_id": 4801717},
]

# ESPN's headshot CDN, keyed by the player id above. Verified against ESPN's
# own player-search API (site.web.api.espn.com) - each id below is that
# player specifically, matched on name + school, not a guess.
def espn_headshot(espn_id):
    return f"https://a.espncdn.com/i/headshots/college-football/players/full/{espn_id}.png"

# Durable identity links, not re-fetched every run. Wikipedia is omitted for
# names without a page rather than guessed; same for any social account that
# couldn't be verified as actually theirs.
REFERENCES = {}

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
NEWS_FLOOR = 16
NEWS_MAX = 8

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_MARKETS = [
    {"key": "first_pick_player", "title": "First player picked, 2027 NFL Draft",
     "event_ticker": "KXNFLDRAFTPICK-27-1",
     "url": "https://kalshi.com/markets/kxnfldraftpick/nfl-draft-pick/kxnfldraftpick-27-1"},
    {"key": "first_team_to_pick", "title": "First team to pick, 2027 NFL Draft",
     "event_ticker": "KXNFLDRAFT1ST-27",
     "url": "https://kalshi.com/markets/kxnfldraft1st/make-the-1st-pick-in-nfl-draft/kxnfldraft1st-27"},
    {"key": "heisman", "title": "2027 Heisman Trophy winner",
     "event_ticker": "KXHEISMAN-27",
     "url": "https://kalshi.com/markets/kxheisman/heisman-trophy-winner/kxheisman-27"},
]
KALSHI_TOP_N = 8

DIAG = {"errors": [], "notes": []}
UA = {"User-Agent": "browns-savior-watch/2.0"}


def cfbd(path, **params):
    """GET a CFBD endpoint. Returns parsed JSON, or None after logging why not."""
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{CFBD}{path}" + (f"?{q}" if q else "")
    head = dict(UA)
    head["Authorization"] = f"Bearer {KEY}"
    head["Accept"] = "application/json"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=head), timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                DIAG["errors"].append(f"{path}: HTTP {e.code} - key rejected or tier too low")
                return None
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            DIAG["errors"].append(f"{path}: HTTP {e.code}")
            return None
        except Exception as e:
            if attempt == 2:
                DIAG["errors"].append(f"{path}: {e}")
                return None
            time.sleep(2 * (attempt + 1))


def get_text(url, tries=2):
    for i in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(2)


def now_utc():
    return datetime.now(timezone.utc)


def parse_dt(s):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

def resolve_teams(prev):
    teams = dict(prev or {})
    if all(q["school"] in teams for q in QBS):
        return teams
    rows = cfbd("/teams/fbs", year=SEASON)
    if not rows:
        return teams
    index = {}
    for t in rows:
        for k in (t.get("school"), t.get("abbreviation"), t.get("alternateName")):
            if k:
                index.setdefault(str(k).lower(), t)
    for q in QBS:
        if q["school"] in teams:
            continue
        hit = index.get(q["school"].lower())
        if not hit:
            DIAG["errors"].append(f"no CFBD team named {q['school']}")
            continue
        logos = hit.get("logos") or []
        teams[q["school"]] = {
            "id": hit.get("id"),
            "school": hit.get("school"),
            "mascot": hit.get("mascot"),
            "logo": logos[0] if logos else None,
            "logo_dark": logos[1] if len(logos) > 1 else (logos[0] if logos else None),
            "color": hit.get("color") or "#444444",
        }
    return teams


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------

def season_games():
    rows = cfbd("/games", year=SEASON, seasonType="regular", classification="fbs")
    return rows or []


def live_index():
    """game id -> live status.

    Returns (index, reachable). An empty index with reachable=True simply means
    nothing is being played right now; reachable=False means the endpoint
    refused us, which is the only case worth warning about.
    """
    rows = cfbd("/scoreboard", classification="fbs")
    if rows is None:
        DIAG["notes"].append("scoreboard call failed - live status unavailable this run")
        return {}, False
    return {g.get("id"): g for g in rows if g.get("status") == "in_progress"}, True


def team_games(games, team_id):
    out = [g for g in games if g.get("homeId") == team_id or g.get("awayId") == team_id]
    out.sort(key=lambda g: g.get("startDate") or "")
    return out


def shape(game, team_id, live=None):
    """Turn a CFBD game into the status object the page renders."""
    home = game.get("homeId") == team_id
    mine = game.get("homePoints") if home else game.get("awayPoints")
    theirs = game.get("awayPoints") if home else game.get("homePoints")
    opp = game.get("awayTeam") if home else game.get("homeTeam")
    out = {
        "event_id": str(game.get("id")),
        "week": game.get("week"),
        "opponent": opp,
        "opponent_id": game.get("awayId") if home else game.get("homeId"),
        "home_away": "vs" if home else "at",
        "kickoff": game.get("startDate"),
        "tbd": bool(game.get("startTimeTBD")),
        "neutral": bool(game.get("neutralSite")),
    }
    if live:
        lm = live.get("homeTeam") if home else live.get("awayTeam")
        lt = live.get("awayTeam") if home else live.get("homeTeam")
        out.update({
            "state": "live",
            "period": live.get("period"),
            "clock": live.get("clock"),
            "tv": live.get("tv"),
            "score": f"{(lm or {}).get('points', 0)}-{(lt or {}).get('points', 0)}",
            "label": f"{out['home_away']} {opp}",
        })
    elif game.get("completed") and mine is not None and theirs is not None:
        res = "W" if mine > theirs else ("L" if mine < theirs else "T")
        out.update({"state": "final", "result": res, "score": f"{mine}-{theirs}",
                    "label": f"{res} {mine}-{theirs} {out['home_away']} {opp}"})
    else:
        out.update({"state": "scheduled", "label": f"{out['home_away']} {opp}"})
    return out


def this_week(games, team_id, live_games):
    """The game that belongs on today's board: live, else most recent final, else next up."""
    n = now_utc()
    window = [g for g in team_games(games, team_id)
              if (d := parse_dt(g.get("startDate"))) and -timedelta(days=4) <= d - n <= timedelta(days=3)]
    for g in window:
        if g.get("id") in live_games:
            return shape(g, team_id, live_games[g["id"]])
    finals = [g for g in window if g.get("completed")]
    if finals:
        return shape(finals[-1], team_id)
    if window:
        return shape(window[0], team_id)
    return {"state": "idle", "label": "No game this week"}


def upcoming(games, team_id):
    n = now_utc()
    for g in team_games(games, team_id):
        d = parse_dt(g.get("startDate"))
        if g.get("completed") or not d or d <= n:
            continue
        return shape(g, team_id)
    return None


# ---------------------------------------------------------------------------
# Box scores
# ---------------------------------------------------------------------------

def to_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return 0


def box_line(week, school, player):
    """Passing and rushing line from /games/players."""
    rows = cfbd("/games/players", year=SEASON, week=week, team=school,
                seasonType="regular", classification="fbs")
    if not rows:
        return None
    last = player.split()[-1].lower()
    line = {}
    for game in rows:
        for team in game.get("teams", []):
            if (team.get("team") or "").lower() != school.lower():
                continue
            for cat in team.get("categories", []):
                cname = (cat.get("name") or "").lower()
                if cname not in ("passing", "rushing"):
                    continue
                for typ in cat.get("types", []):
                    tname = (typ.get("name") or "").upper()
                    for ath in typ.get("athletes", []):
                        if last not in (ath.get("name") or "").lower():
                            continue
                        val = ath.get("stat")
                        if cname == "passing":
                            if tname in ("C/ATT", "COMPLETIONS/ATTEMPTS"):
                                c, _, a = str(val).partition("/")
                                line["cmp"], line["att"] = to_int(c), to_int(a)
                            elif tname == "YDS":
                                line["pass_yds"] = to_int(val)
                            elif tname == "TD":
                                line["pass_td"] = to_int(val)
                            elif tname == "INT":
                                line["int"] = to_int(val)
                            elif tname == "QBR":
                                line["qbr"] = val
                        else:
                            if tname == "CAR":
                                line["rush_att"] = to_int(val)
                            elif tname == "YDS":
                                line["rush_yds"] = to_int(val)
                            elif tname == "TD":
                                line["rush_td"] = to_int(val)
    if line.get("att"):
        line["comp_pct"] = round(100 * line.get("cmp", 0) / line["att"], 1)
        line["ypa"] = round(line.get("pass_yds", 0) / line["att"], 1)
    return line or None


# ---------------------------------------------------------------------------
# Season accumulation
# ---------------------------------------------------------------------------

def clean_log(log):
    return [g for g in (log or []) if str(g.get("event_id", "")).isdigit()]


def merge_log(prev_log, status, line):
    log = clean_log(prev_log)
    if status.get("state") != "final" or not line or not line.get("att"):
        return log
    entry = dict(line)
    entry.update({k: status.get(k) for k in
                  ("event_id", "week", "opponent", "home_away", "result", "score")})
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
    t = {k: sum(to_int(g.get(k)) for g in log) for k in
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


def epa_for(school, player):
    rows = cfbd("/ppa/players/season", year=SEASON, team=school, excludeGarbageTime="true")
    for r in rows or []:
        if player.split()[-1].lower() in (r.get("name") or "").lower():
            v = (r.get("averagePPA") or {}).get("all")
            if v is not None:
                return round(v, 3)
    return None


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def build_news():
    seen, out = set(), []
    for qb in QBS:
        q = urllib.parse.quote(f'"{qb["name"]}" {qb["school"]} football')
        xml = get_text(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")
        if not xml:
            continue
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            continue
        for it in root.iter("item"):
            src = it.find("source")
            domain = ""
            if src is not None:
                domain = re.sub(r"^https?://(www\.)?", "", src.get("url", "")).split("/")[0]
            head = (it.findtext("title") or "").strip().rsplit(" - ", 1)[0]
            key = re.sub(r"[^a-z0-9]", "", head.lower())[:60]
            if not head or key in seen:
                continue
            seen.add(key)
            item = {"headline": head, "source": (src.text if src is not None else domain),
                    "domain": domain, "url": (it.findtext("link") or "").strip(),
                    "player": qb["name"]}
            score = SOURCE_TIER.get(domain, 1) * 2
            for word, w in HIGH_SIGNAL:
                if word in head.lower():
                    score += w
            try:
                pub = datetime.strptime((it.findtext("pubDate") or "").strip(),
                                        "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
                age = (now_utc() - pub).total_seconds() / 3600
                score += 7 if age < 24 else 3 if age < 72 else 0
                item["age_hours"] = round(age)
            except Exception:
                item["age_hours"] = None
            item["score"] = score
            if score >= NEWS_FLOOR:
                out.append(item)
    out.sort(key=lambda x: -x["score"])
    return out[:NEWS_MAX]


# ---------------------------------------------------------------------------
# Kalshi prediction markets
# ---------------------------------------------------------------------------

def kalshi_event(event_ticker):
    url = f"{KALSHI}/events/{event_ticker}?with_nested_markets=true"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            DIAG["errors"].append(f"kalshi {event_ticker}: HTTP {e.code}")
            return None
        except Exception as e:
            if attempt == 2:
                DIAG["errors"].append(f"kalshi {event_ticker}: {e}")
                return None
            time.sleep(2 * (attempt + 1))


def build_kalshi():
    tracked_last = {qb["name"].split()[-1].lower() for qb in QBS}
    out = []
    for spec in KALSHI_MARKETS:
        data = kalshi_event(spec["event_ticker"])
        markets = ((data or {}).get("event") or {}).get("markets") or []
        rows = []
        for m in markets:
            if m.get("status") != "active":
                continue
            name = m.get("yes_sub_title") or m.get("subtitle") or m.get("title")
            try:
                pct = round(float(m.get("last_price_dollars") or 0) * 100)
            except (TypeError, ValueError):
                continue
            if not name:
                continue
            rows.append({"name": name,
                         "pct": pct,
                         "tracked": name.split()[-1].lower() in tracked_last})
        if not rows and data is None:
            continue
        rows.sort(key=lambda r: -r["pct"])
        top, rest = rows[:KALSHI_TOP_N], rows[KALSHI_TOP_N:]
        out.append({
            "key": spec["key"], "title": spec["title"], "url": spec["url"],
            "candidates": top,
            "field_pct": max(0, 100 - sum(r["pct"] for r in top)) if rest else None,
            "field_count": len(rest),
        })
    return out


# ---------------------------------------------------------------------------

def main():
    n = now_utc()
    print(f"Fetching {n.isoformat()}")
    if not KEY:
        print("FATAL: CFBD_API_KEY is not set. Add it as a repository secret.",
              file=sys.stderr)
        sys.exit(1)

    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT))
        except Exception:
            pass
    prev_qb = {q["name"]: q for q in prev.get("quarterbacks", [])}
    run_daily = os.environ.get("FORCE_DAILY") == "1" or n.hour == 12 or not prev_qb

    teams = resolve_teams(prev.get("teams"))
    print(f"  teams resolved: {len(teams)}/{len(QBS)}")
    games = season_games()
    print(f"  {len(games)} FBS games in the {SEASON} schedule")
    live, live_ok = live_index()
    print(f"  scoreboard reachable: {live_ok}; "
          f"{len(live)} games in progress league-wide")

    rows, matched = [], 0
    for qb in QBS:
        team = teams.get(qb["school"])
        old = prev_qb.get(qb["name"], {})
        log = clean_log(old.get("log"))
        if not team:
            rows.append({"name": qb["name"], "school": qb["school"], "class": qb["cls"],
                         "headshot": espn_headshot(qb["espn_id"]),
                         "team": None, "status": {"state": "idle", "label": "Team unresolved"},
                         "game": None, "next_game": None, "log": log,
                         "season": season_from_log(log)})
            continue

        status = this_week(games, team["id"], live)
        if status["state"] != "idle":
            matched += 1

        line = old.get("game")
        need = status["state"] == "final" and not any(
            e.get("event_id") == status.get("event_id") for e in log)
        if need or (status["state"] == "live" and status.get("period")):
            line = box_line(status.get("week"), team["school"], qb["name"]) or line
        elif status["state"] not in ("live", "final"):
            line = None

        log = merge_log(log, status, line)
        epa = epa_for(team["school"], qb["name"]) if run_daily \
            else (old.get("season") or {}).get("epa_per_play")

        print(f"  {qb['name']:<20} {status['state']:<10} {status.get('label','')}")
        rows.append({"name": qb["name"], "school": qb["school"], "class": qb["cls"],
                     "headshot": espn_headshot(qb["espn_id"]),
                     "team": team, "status": status, "game": line,
                     "next_game": upcoming(games, team["id"]),
                     "log": log, "season": season_from_log(log, epa)})

    kalshi = build_kalshi()
    references = {qb["name"]: REFERENCES[qb["name"]] for qb in QBS if qb["name"] in REFERENCES}

    payload = {
        "updated_at": n.isoformat(), "season": SEASON,
        "live_count": sum(1 for r in rows if r["status"]["state"] == "live"),
        "teams": teams, "quarterbacks": rows, "news": build_news(),
        "kalshi": kalshi, "references": references,
        "diagnostics": {**DIAG, "games_seen": len(games), "games_matched": matched,
                        "teams_resolved": len(teams), "live_available": live_ok,
                        "live_games_now": len(live)},
    }
    json.dump(payload, open(OUT, "w"), indent=2)
    print(f"Wrote {OUT} - {matched}/{len(QBS)} on the board, "
          f"{sum(len(r['log']) for r in rows)} games logged, "
          f"{len(payload['news'])} news items, {len(kalshi)}/3 Kalshi markets")
    if DIAG["errors"] or DIAG["notes"]:
        print("Notes:")
        for m in (DIAG["errors"] + DIAG["notes"])[:12]:
            print(f"  - {m}")


if __name__ == "__main__":
    main()
