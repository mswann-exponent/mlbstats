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
