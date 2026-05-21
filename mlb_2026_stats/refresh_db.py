# refresh_db.py
# Run this once from terminal: python refresh_db.py
# This drops all tables and re-initializes so you start clean,
# then you can re-run whatever script populates your data.

import sqlite3
import os
from models import DB_PATH, init_db

def nuke_and_rebuild():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[refresh_db] Deleted existing database at {DB_PATH}")
    else:
        print(f"[refresh_db] No existing database found at {DB_PATH}, creating fresh.")

    init_db()
    print("[refresh_db] Database re-initialized successfully.")
    print("[refresh_db] Now run your data ingestion script to repopulate stats.")

if __name__ == "__main__":
    nuke_and_rebuild()