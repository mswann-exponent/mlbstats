import requests
import certifi
import urllib3
import time
from datetime import datetime, timedelta
from models import init_db, get_conn

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://statsapi.mlb.com/api/v1"
RECENT_DAYS_TO_REFRESH = 3


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

        recent_cutoff = (datetime.today() - timedelta(days=RECENT_DAYS_TO_REFRESH)).date().isoformat()

        if incremental:
            games = [
                g for g in games
                if g["gamePk"] not in existing_ids or g["gameDate"] >= recent_cutoff
            ]

        print(f"{len(games)} games remaining after incremental filter")
        print(f"Refreshing all games on or after {recent_cutoff}")

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