from pathlib import Path
import textwrap

project_name = "mlb_2026_stats"
base = Path(project_name)
(base / "templates").mkdir(parents=True, exist_ok=True)
(base / "static").mkdir(parents=True, exist_ok=True)

files = {
    "requirements.txt": r'''
Flask==3.0.3
requests==2.31.0
urllib3==1.26.18
certifi==2024.8.30
''',

    "models.py": r'''
import sqlite3
from pathlib import Path

DB_PATH = Path("stats.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS players (
        player_id INTEGER PRIMARY KEY,
        full_name TEXT,
        current_team TEXT,
        position TEXT,
        bats TEXT,
        throws TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS player_game_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER,
        game_pk INTEGER,
        game_date TEXT,
        season TEXT,
        team TEXT,
        opponent TEXT,
        stat_group TEXT,

        games INTEGER DEFAULT 1,

        at_bats INTEGER DEFAULT 0,
        runs INTEGER DEFAULT 0,
        hits INTEGER DEFAULT 0,
        doubles INTEGER DEFAULT 0,
        triples INTEGER DEFAULT 0,
        home_runs INTEGER DEFAULT 0,
        rbi INTEGER DEFAULT 0,
        stolen_bases INTEGER DEFAULT 0,
        walks INTEGER DEFAULT 0,
        strikeouts INTEGER DEFAULT 0,
        hit_by_pitch INTEGER DEFAULT 0,

        innings_pitched REAL DEFAULT 0,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        saves INTEGER DEFAULT 0,
        earned_runs INTEGER DEFAULT 0,
        hits_allowed INTEGER DEFAULT 0,
        walks_allowed INTEGER DEFAULT 0,
        pitching_strikeouts INTEGER DEFAULT 0,

        UNIQUE(player_id, game_pk, stat_group)
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_pgs_season ON player_game_stats(season)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pgs_game_date ON player_game_stats(game_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pgs_player ON player_game_stats(player_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pgs_gamepk ON player_game_stats(game_pk)")

    conn.commit()
    conn.close()
''',

    "sync_stats.py": r'''
import requests
import certifi
import urllib3
import time
from models import init_db, get_conn

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://statsapi.mlb.com/api/v1"

def safe_get(url, params=None, timeout=30):
    try:
        try:
            r = requests.get(url, params=params, timeout=timeout, verify=certifi.where())
            r.raise_for_status()
        except requests.exceptions.SSLError:
            r = requests.get(url, params=params, timeout=timeout, verify=False)
            r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"Request failed: {url} params={params} error={e}")
        return None

def get_schedule(season="2026", start_date=None, end_date=None):
    params = {
        "sportId": 1,
        "season": season,
        "gameType": "R"
    }

    if start_date and end_date:
        params["startDate"] = start_date
        params["endDate"] = end_date

    data = safe_get(f"{BASE_URL}/schedule", params=params)
    if not data:
        return []

    games = []
    for date_block in data.get("dates", []):
        for game in date_block.get("games", []):
            games.append({
                "gamePk": game.get("gamePk"),
                "gameDate": date_block.get("date"),
                "status": game.get("status", {}).get("detailedState", "")
            })

    return games

def get_boxscore(game_pk):
    return safe_get(f"{BASE_URL}/game/{game_pk}/boxscore")

def get_db_connection():
    conn = get_conn()
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

def parse_innings(ip_str):
    if not ip_str:
        return 0.0

    try:
        if "." in str(ip_str):
            whole, frac = str(ip_str).split(".")
            whole = int(whole)
            frac = int(frac)

            if frac == 0:
                return float(whole)
            if frac == 1:
                return whole + (1 / 3)
            if frac == 2:
                return whole + (2 / 3)

        return float(ip_str)
    except Exception:
        return 0.0

def upsert_player(cur, player_id, full_name, current_team, position, bats, throws):
    cur.execute("""
        INSERT INTO players (player_id, full_name, current_team, position, bats, throws)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            full_name = excluded.full_name,
            current_team = excluded.current_team,
            position = excluded.position,
            bats = excluded.bats,
            throws = excluded.throws
    """, (player_id, full_name, current_team, position, bats, throws))

def upsert_game_stat(cur, row):
    cur.execute("""
        INSERT INTO player_game_stats (
            player_id, game_pk, game_date, season, team, opponent, stat_group,
            games, at_bats, runs, hits, doubles, triples, home_runs, rbi, stolen_bases,
            walks, strikeouts, hit_by_pitch, innings_pitched, wins, losses, saves,
            earned_runs, hits_allowed, walks_allowed, pitching_strikeouts
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id, game_pk, stat_group) DO UPDATE SET
            game_date = excluded.game_date,
            season = excluded.season,
            team = excluded.team,
            opponent = excluded.opponent,
            games = excluded.games,
            at_bats = excluded.at_bats,
            runs = excluded.runs,
            hits = excluded.hits,
            doubles = excluded.doubles,
            triples = excluded.triples,
            home_runs = excluded.home_runs,
            rbi = excluded.rbi,
            stolen_bases = excluded.stolen_bases,
            walks = excluded.walks,
            strikeouts = excluded.strikeouts,
            hit_by_pitch = excluded.hit_by_pitch,
            innings_pitched = excluded.innings_pitched,
            wins = excluded.wins,
            losses = excluded.losses,
            saves = excluded.saves,
            earned_runs = excluded.earned_runs,
            hits_allowed = excluded.hits_allowed,
            walks_allowed = excluded.walks_allowed,
            pitching_strikeouts = excluded.pitching_strikeouts
    """, (
        row["player_id"],
        row["game_pk"],
        row["game_date"],
        row["season"],
        row["team"],
        row["opponent"],
        row["stat_group"],
        row["games"],
        row["at_bats"],
        row["runs"],
        row["hits"],
        row["doubles"],
        row["triples"],
        row["home_runs"],
        row["rbi"],
        row["stolen_bases"],
        row["walks"],
        row["strikeouts"],
        row["hit_by_pitch"],
        row["innings_pitched"],
        row["wins"],
        row["losses"],
        row["saves"],
        row["earned_runs"],
        row["hits_allowed"],
        row["walks_allowed"],
        row["pitching_strikeouts"]
    ))

def process_team_players(cur, team_players, team_name, opponent_name, game_pk, game_date, season):
    for _, player_wrapper in team_players.items():
        person = player_wrapper.get("person", {})
        stats = player_wrapper.get("stats", {})
        batting = stats.get("batting", {})
        pitching = stats.get("pitching", {})

        player_id = person.get("id")
        if not player_id:
            continue

        full_name = person.get("fullName", "")
        position = player_wrapper.get("position", {}).get("abbreviation", "")
        bats = person.get("batSide", {}).get("code", "")
        throws = person.get("pitchHand", {}).get("code", "")

        upsert_player(cur, player_id, full_name, team_name, position, bats, throws)

        has_hitting = any([
            batting.get("atBats"),
            batting.get("hits"),
            batting.get("homeRuns"),
            batting.get("baseOnBalls"),
            batting.get("runs"),
            batting.get("rbi")
        ])

        if has_hitting:
            upsert_game_stat(cur, {
                "player_id": player_id,
                "game_pk": game_pk,
                "game_date": game_date,
                "season": season,
                "team": team_name,
                "opponent": opponent_name,
                "stat_group": "hitting",
                "games": 1,
                "at_bats": int(batting.get("atBats", 0) or 0),
                "runs": int(batting.get("runs", 0) or 0),
                "hits": int(batting.get("hits", 0) or 0),
                "doubles": int(batting.get("doubles", 0) or 0),
                "triples": int(batting.get("triples", 0) or 0),
                "home_runs": int(batting.get("homeRuns", 0) or 0),
                "rbi": int(batting.get("rbi", 0) or 0),
                "stolen_bases": int(batting.get("stolenBases", 0) or 0),
                "walks": int(batting.get("baseOnBalls", 0) or 0),
                "strikeouts": int(batting.get("strikeOuts", 0) or 0),
                "hit_by_pitch": int(batting.get("hitByPitch", 0) or 0),
                "innings_pitched": 0.0,
                "wins": 0,
                "losses": 0,
                "saves": 0,
                "earned_runs": 0,
                "hits_allowed": 0,
                "walks_allowed": 0,
                "pitching_strikeouts": 0
            })

        has_pitching = any([
            pitching.get("inningsPitched"),
            pitching.get("strikeOuts"),
            pitching.get("baseOnBalls"),
            pitching.get("earnedRuns"),
            pitching.get("hits"),
            pitching.get("wins"),
            pitching.get("losses"),
            pitching.get("saves")
        ])

        if has_pitching:
            upsert_game_stat(cur, {
                "player_id": player_id,
                "game_pk": game_pk,
                "game_date": game_date,
                "season": season,
                "team": team_name,
                "opponent": opponent_name,
                "stat_group": "pitching",
                "games": 1,
                "at_bats": 0,
                "runs": 0,
                "hits": 0,
                "doubles": 0,
                "triples": 0,
                "home_runs": 0,
                "rbi": 0,
                "stolen_bases": 0,
                "walks": 0,
                "strikeouts": 0,
                "hit_by_pitch": 0,
                "innings_pitched": parse_innings(pitching.get("inningsPitched", "0.0")),
                "wins": int(pitching.get("wins", 0) or 0),
                "losses": int(pitching.get("losses", 0) or 0),
                "saves": int(pitching.get("saves", 0) or 0),
                "earned_runs": int(pitching.get("earnedRuns", 0) or 0),
                "hits_allowed": int(pitching.get("hits", 0) or 0),
                "walks_allowed": int(pitching.get("baseOnBalls", 0) or 0),
                "pitching_strikeouts": int(pitching.get("strikeOuts", 0) or 0)
            })

def process_game(conn, cur, game):
    game_pk = game["gamePk"]
    game_date = game["gameDate"]
    season = str(game_date[:4])

    box = get_boxscore(game_pk)
    if not box:
        return False

    teams = box.get("teams", {})
    home = teams.get("home", {})
    away = teams.get("away", {})

    home_name = home.get("team", {}).get("name", "Home")
    away_name = away.get("team", {}).get("name", "Away")

    process_team_players(cur, home.get("players", {}), home_name, away_name, game_pk, game_date, season)
    process_team_players(cur, away.get("players", {}), away_name, home_name, game_pk, game_date, season)

    conn.commit()
    return True

def get_existing_game_ids(cur, season):
    cur.execute("SELECT DISTINCT game_pk FROM player_game_stats WHERE season = ?", (season,))
    return {row[0] for row in cur.fetchall()}

def run_sync(season="2026", start_date=None, end_date=None, limit=None, incremental=True):
    init_db()
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        games = get_schedule(season=season, start_date=start_date, end_date=end_date)

        if limit:
            games = games[:limit]

        print(f"Found {len(games)} scheduled games for season {season}")

        existing_ids = get_existing_game_ids(cur, season) if incremental else set()
        if incremental:
            games = [g for g in games if g["gamePk"] not in existing_ids]

        print(f"{len(games)} games remaining after incremental filter")

        processed = 0
        skipped = 0

        for i, game in enumerate(games, start=1):
            try:
                status = (game.get("status") or "").lower()
                if "scheduled" in status or "pre-game" in status:
                    skipped += 1
                    continue

                ok = process_game(conn, cur, game)
                if ok:
                    processed += 1
            except Exception as e:
                print(f"Game processing failed for {game.get('gamePk')}: {e}")

            if i % 25 == 0 or i == len(games):
                print(f"Checked {i}/{len(games)} games | processed={processed} skipped={skipped}")

            time.sleep(0.02)

        print(f"Sync complete | processed={processed} skipped={skipped}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_sync(season="2026", incremental=True)
''',

    "app.py": r'''
from flask import Flask, render_template, request, jsonify, Response
import csv
import io
from datetime import date, timedelta
from models import init_db, get_conn

app = Flask(__name__)

def build_where_clause(season, start_date, end_date):
    clauses = []
    params = []

    if season:
        clauses.append("pgs.season = ?")
        params.append(season)

    if start_date:
        clauses.append("pgs.game_date >= ?")
        params.append(start_date)

    if end_date:
        clauses.append("pgs.game_date <= ?")
        params.append(end_date)

    where_sql = "WHERE " + " AND ".join(clauses) if clauses else ""
    return where_sql, params

def get_aggregated_stats(season="2026", start_date=None, end_date=None):
    conn = get_conn()
    cur = conn.cursor()

    where_sql, params = build_where_clause(season, start_date, end_date)

    query = f"""
    SELECT
        p.player_id,
        p.full_name,
        p.current_team,
        p.position,
        p.bats,
        p.throws,

        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.games ELSE 0 END) as hitting_games,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.at_bats ELSE 0 END) as at_bats,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.runs ELSE 0 END) as runs,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.hits ELSE 0 END) as hits,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.doubles ELSE 0 END) as doubles,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.triples ELSE 0 END) as triples,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.home_runs ELSE 0 END) as home_runs,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.rbi ELSE 0 END) as rbi,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.stolen_bases ELSE 0 END) as stolen_bases,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.walks ELSE 0 END) as walks,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.strikeouts ELSE 0 END) as hitting_strikeouts,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.hit_by_pitch ELSE 0 END) as hit_by_pitch,

        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.games ELSE 0 END) as pitching_games,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.innings_pitched ELSE 0 END) as innings_pitched,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.wins ELSE 0 END) as wins,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.losses ELSE 0 END) as losses,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.saves ELSE 0 END) as saves,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.earned_runs ELSE 0 END) as earned_runs,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.hits_allowed ELSE 0 END) as hits_allowed,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.walks_allowed ELSE 0 END) as walks_allowed,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.pitching_strikeouts ELSE 0 END) as pitching_strikeouts

    FROM player_game_stats pgs
    JOIN players p ON p.player_id = pgs.player_id
    {where_sql}
    GROUP BY p.player_id, p.full_name, p.current_team, p.position, p.bats, p.throws
    ORDER BY p.full_name
    """

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    result = []
    for row in rows:
        ab = row["at_bats"] or 0
        hits = row["hits"] or 0
        walks = row["walks"] or 0
        hbp = row["hit_by_pitch"] or 0
        doubles = row["doubles"] or 0
        triples = row["triples"] or 0
        home_runs = row["home_runs"] or 0

        singles = hits - doubles - triples - home_runs
        total_bases = singles + (doubles * 2) + (triples * 3) + (home_runs * 4)

        avg = round(hits / ab, 3) if ab > 0 else 0
        obp_den = ab + walks + hbp
        obp = round((hits + walks + hbp) / obp_den, 3) if obp_den > 0 else 0
        slg = round(total_bases / ab, 3) if ab > 0 else 0
        ops = round(obp + slg, 3)

        ip = row["innings_pitched"] or 0
        er = row["earned_runs"] or 0
        hits_allowed = row["hits_allowed"] or 0
        walks_allowed = row["walks_allowed"] or 0

        era = round((er * 9) / ip, 2) if ip > 0 else 0
        whip = round((walks_allowed + hits_allowed) / ip, 3) if ip > 0 else 0

        total_so = (row["hitting_strikeouts"] or 0) + (row["pitching_strikeouts"] or 0)

        result.append({
            "player_id": row["player_id"],
            "full_name": row["full_name"],
            "current_team": row["current_team"],
            "position": row["position"],
            "bats": row["bats"],
            "throws": row["throws"],
            "hitting_games": row["hitting_games"] or 0,
            "at_bats": ab,
            "runs": row["runs"] or 0,
            "hits": hits,
            "doubles": doubles,
            "triples": triples,
            "home_runs": home_runs,
            "rbi": row["rbi"] or 0,
            "stolen_bases": row["stolen_bases"] or 0,
            "walks": walks,
            "hitting_strikeouts": row["hitting_strikeouts"] or 0,
            "avg": avg,
            "obp": obp,
            "slg": slg,
            "ops": ops,
            "pitching_games": row["pitching_games"] or 0,
            "innings_pitched": round(ip, 3),
            "wins": row["wins"] or 0,
            "losses": row["losses"] or 0,
            "saves": row["saves"] or 0,
            "earned_runs": er,
            "hits_allowed": hits_allowed,
            "walks_allowed": walks_allowed,
            "pitching_strikeouts": row["pitching_strikeouts"] or 0,
            "total_strikeouts": total_so,
            "era": era,
            "whip": whip
        })

    return result

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/stats")
def api_stats():
    season = request.args.get("season", "2026")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    data = get_aggregated_stats(season=season, start_date=start_date, end_date=end_date)
    return jsonify({
        "count": len(data),
        "players": data
    })

@app.route("/download.csv")
def download_csv():
    season = request.args.get("season", "2026")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    data = get_aggregated_stats(season=season, start_date=start_date, end_date=end_date)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Player",
        "Team",
        "Pos",
        "H",
        "HR",
        "RBI",
        "AVG",
        "R",
        "SB",
        "W",
        "SO",
        "SV"
    ])

    for p in data:
        writer.writerow([
            p["full_name"],
            p["current_team"],
            p["position"],
            p["hits"],
            p["home_runs"],
            p["rbi"],
            f'{p["avg"]:.3f}',
            p["runs"],
            p["stolen_bases"],
            p["wins"],
            p["total_strikeouts"],
            p["saves"]
        ])

    filename = f"mlb_aggregate_stats_{season}.csv"
    if start_date and end_date:
        filename = f"mlb_aggregate_stats_{season}_{start_date}_to_{end_date}.csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route("/api/date-presets")
def date_presets():
    today = date.today()
    last_7 = today - timedelta(days=7)
    last_30 = today - timedelta(days=30)

    return jsonify({
        "today": today.isoformat(),
        "last_7": last_7.isoformat(),
        "last_30": last_30.isoformat()
    })

if __name__ == "__main__":
    init_db()
    app.run(debug=False, use_reloader=False)
''',

    "templates/index.html": r'''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MLB 2026 Aggregate Player Stats</title>
  <style>
    :root {
      --bg: #0b1220;
      --panel: #121a2b;
      --panel-2: #182235;
      --border: #2b3a55;
      --text: #e5edf9;
      --muted: #9db0d0;
      --accent: #3b82f6;
      --accent-2: #2563eb;
      --success: #10b981;
      --shadow: 0 10px 25px rgba(0,0,0,0.25);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: Inter, Arial, sans-serif;
      background: linear-gradient(180deg, #09111d 0%, #0b1220 100%);
      color: var(--text);
    }

    header {
      padding: 28px 24px 18px;
      border-bottom: 1px solid var(--border);
      background: rgba(18, 26, 43, 0.95);
      backdrop-filter: blur(6px);
      position: sticky;
      top: 0;
      z-index: 5;
    }

    .header-inner {
      max-width: 1400px;
      margin: 0 auto;
    }

    h1 {
      margin: 0 0 6px 0;
      font-size: 30px;
      letter-spacing: 0.2px;
    }

    .subtitle {
      color: var(--muted);
      margin-bottom: 18px;
      font-size: 14px;
    }

    .controls-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      box-shadow: var(--shadow);
    }

    .controls {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: end;
    }

    .field {
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-width: 150px;
    }

    .field label {
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    input, select, button {
      padding: 11px 12px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      font-size: 14px;
    }

    button {
      background: var(--accent);
      border: none;
      cursor: pointer;
      font-weight: 600;
      transition: transform .15s ease, background .15s ease;
    }

    button:hover {
      background: var(--accent-2);
      transform: translateY(-1px);
    }

    .secondary {
      background: #24324d;
    }

    .secondary:hover {
      background: #304160;
    }

    .container {
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }

    .quick-buttons {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 16px;
    }

    .status {
      margin-bottom: 16px;
      color: var(--muted);
      font-size: 14px;
    }

    .table-wrap {
      overflow: auto;
      max-height: 75vh;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }

    th, td {
      padding: 10px 10px;
      border-bottom: 1px solid rgba(43, 58, 85, 0.7);
      white-space: nowrap;
      text-align: center;
    }

    th {
      position: sticky;
      top: 0;
      background: #162033;
      z-index: 1;
      cursor: pointer;
      user-select: none;
    }

    th:hover {
      background: #1b2940;
    }

    td.name, th.name,
    td.team, th.team,
    td.pos, th.pos {
      text-align: left;
    }

    tr:hover td {
      background: rgba(59, 130, 246, 0.06);
    }

    .pill {
      display: inline-block;
      background: rgba(16, 185, 129, 0.12);
      color: #7ef0c3;
      border: 1px solid rgba(16, 185, 129, 0.25);
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      margin-left: 8px;
    }

    .footer-note {
      margin-top: 12px;
      color: var(--muted);
      font-size: 12px;
    }
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <h1>MLB Aggregate Player Stats <span class="pill">2026 Ready</span></h1>
      <div class="subtitle">Aggregate hitting and pitching stats by season or date range, with sortable columns and CSV export.</div>

      <div class="controls-card">
        <div class="controls">
          <div class="field">
            <label for="season">Season</label>
            <select id="season">
              <option value="2026" selected>2026</option>
              <option value="2025">2025</option>
              <option value="2024">2024</option>
              <option value="2023">2023</option>
            </select>
          </div>

          <div class="field">
            <label for="start_date">Start Date</label>
            <input type="date" id="start_date">
          </div>

          <div class="field">
            <label for="end_date">End Date</label>
            <input type="date" id="end_date">
          </div>

          <button onclick="loadStats()">Load Stats</button>
          <button class="secondary" onclick="downloadCSV()">Download CSV</button>
        </div>
      </div>
    </div>
  </header>

  <div class="container">
    <div class="quick-buttons">
      <button class="secondary" onclick="setSeasonToDate()">Season to Date</button>
      <button class="secondary" onclick="setLast7Days()">Last 7 Days</button>
      <button class="secondary" onclick="setLast30Days()">Last 30 Days</button>
      <button class="secondary" onclick="clearDates()">Clear Dates</button>
    </div>

    <div class="status" id="status">Loading stats...</div>

    <div class="table-wrap">
      <table id="statsTable">
        <thead>
          <tr>
            <th class="name" data-key="full_name">Player</th>
            <th class="team" data-key="current_team">Team</th>
            <th class="pos" data-key="position">Pos</th>
            <th data-key="hits">H</th>
            <th data-key="home_runs">HR</th>
            <th data-key="rbi">RBI</th>
            <th data-key="avg">AVG</th>
            <th data-key="runs">R</th>
            <th data-key="stolen_bases">SB</th>
            <th data-key="wins">W</th>
            <th data-key="total_strikeouts">SO</th>
            <th data-key="saves">SV</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>

    <div class="footer-note">
      Click any column header to sort. Data loads automatically on page open.
    </div>
  </div>

  <script src="/static/app.js"></script>
</body>
</html>
''',

    "static/app.js": r'''
let currentPlayers = [];
let currentSortKey = "hits";
let currentSortDir = "desc";

function getFilters() {
  return {
    season: document.getElementById('season').value,
    start_date: document.getElementById('start_date').value,
    end_date: document.getElementById('end_date').value
  };
}

function buildQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) query.append(key, value);
  });
  return query.toString();
}

function formatDecimal(value, digits = 3) {
  const num = Number(value || 0);
  return num.toFixed(digits);
}

function sortPlayers(players, key, dir) {
  const sorted = [...players].sort((a, b) => {
    const av = a[key];
    const bv = b[key];

    const aNum = Number(av);
    const bNum = Number(bv);
    const bothNumeric = !Number.isNaN(aNum) && !Number.isNaN(bNum);

    let cmp = 0;
    if (bothNumeric) {
      cmp = aNum - bNum;
    } else {
      cmp = String(av ?? "").localeCompare(String(bv ?? ""));
    }

    return dir === "asc" ? cmp : -cmp;
  });

  return sorted;
}

function renderTable(players) {
  const body = document.getElementById('tableBody');
  const sorted = sortPlayers(players, currentSortKey, currentSortDir);

  body.innerHTML = sorted.map(p => `
    <tr>
      <td class="name">${p.full_name || ''}</td>
      <td class="team">${p.current_team || ''}</td>
      <td class="pos">${p.position || ''}</td>
      <td>${p.hits ?? 0}</td>
      <td>${p.home_runs ?? 0}</td>
      <td>${p.rbi ?? 0}</td>
      <td>${formatDecimal(p.avg, 3)}</td>
      <td>${p.runs ?? 0}</td>
      <td>${p.stolen_bases ?? 0}</td>
      <td>${p.wins ?? 0}</td>
      <td>${p.total_strikeouts ?? 0}</td>
      <td>${p.saves ?? 0}</td>
    </tr>
  `).join('');
}

async function loadStats() {
  const filters = getFilters();
  const qs = buildQuery(filters);

  document.getElementById('status').textContent = 'Loading aggregate stats...';

  const res = await fetch(`/api/stats?${qs}`);
  const data = await res.json();

  currentPlayers = data.players || [];
  renderTable(currentPlayers);

  document.getElementById('status').textContent =
    `Loaded ${data.count} aggregate player rows for season ${filters.season}.`;
}

function downloadCSV() {
  const filters = getFilters();
  const qs = buildQuery(filters);
  window.location.href = `/download.csv?${qs}`;
}

async function setLast7Days() {
  const res = await fetch('/api/date-presets');
  const data = await res.json();
  document.getElementById('start_date').value = data.last_7;
  document.getElementById('end_date').value = data.today;
  loadStats();
}

async function setLast30Days() {
  const res = await fetch('/api/date-presets');
  const data = await res.json();
  document.getElementById('start_date').value = data.last_30;
  document.getElementById('end_date').value = data.today;
  loadStats();
}

function setSeasonToDate() {
  const season = document.getElementById('season').value;
  document.getElementById('start_date').value = `${season}-01-01`;
  document.getElementById('end_date').value = '';
  loadStats();
}

function clearDates() {
  document.getElementById('start_date').value = '';
  document.getElementById('end_date').value = '';
  loadStats();
}

function attachSortHandlers() {
  const headers = document.querySelectorAll('#statsTable th[data-key]');
  headers.forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if (currentSortKey === key) {
        currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
      } else {
        currentSortKey = key;
        currentSortDir = 'desc';
      }
      renderTable(currentPlayers);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  attachSortHandlers();
  loadStats();
});
'''
}

for relative_path, content in files.items():
    full_path = base / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

print(f"Project created in ./{project_name}")
print("Next steps:")
print(f"1. cd {project_name}")
print("2. pip install -r requirements.txt")
print("3. For testing, optionally edit sync_stats.py to use season='2023' first")
print("4. python sync_stats.py")
print("5. python app.py")
print("6. Open http://127.0.0.1:5000")