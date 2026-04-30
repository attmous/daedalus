from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_daedalus_db(db_path: Path) -> sqlite3.Connection:
    """Open the Daedalus SQLite state store with production pragmas."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn
