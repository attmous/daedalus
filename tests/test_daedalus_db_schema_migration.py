import importlib.util
import sqlite3
from pathlib import Path


RUNTIME_MODULE_PATH = Path(__file__).resolve().parents[1] / "runtime.py"


def load_runtime_module():
    spec = importlib.util.spec_from_file_location("daedalus_runtime_for_schema_test", RUNTIME_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migrate_schema_identity_renames_relay_runtime_table(tmp_path):
    runtime = load_runtime_module()
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    try:
        # Seed an old-shape DB: relay_runtime table with runtime_id='relay' row
        conn.executescript(
            """
            CREATE TABLE relay_runtime (
                runtime_id TEXT PRIMARY KEY,
                project_key TEXT,
                schema_version INTEGER
            );
            INSERT INTO relay_runtime (runtime_id, project_key, schema_version)
                VALUES ('relay', 'yoyopod', 1);
            """
        )
        conn.commit()

        runtime._migrate_schema_identity(conn)
        conn.commit()

        # Table renamed
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='daedalus_runtime'"
        )
        assert cur.fetchone() is not None
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='relay_runtime'"
        )
        assert cur.fetchone() is None

        # Row's runtime_id updated
        cur = conn.execute(
            "SELECT project_key FROM daedalus_runtime WHERE runtime_id='daedalus'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 'yoyopod'

        cur = conn.execute("SELECT 1 FROM daedalus_runtime WHERE runtime_id='relay'")
        assert cur.fetchone() is None
    finally:
        conn.close()


def test_migrate_schema_identity_idempotent_on_already_migrated_db(tmp_path):
    runtime = load_runtime_module()
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    try:
        # Already-migrated shape
        conn.executescript(
            """
            CREATE TABLE daedalus_runtime (
                runtime_id TEXT PRIMARY KEY,
                project_key TEXT
            );
            INSERT INTO daedalus_runtime (runtime_id, project_key)
                VALUES ('daedalus', 'yoyopod');
            """
        )
        conn.commit()

        runtime._migrate_schema_identity(conn)
        conn.commit()

        cur = conn.execute(
            "SELECT project_key FROM daedalus_runtime WHERE runtime_id='daedalus'"
        )
        assert cur.fetchone()[0] == 'yoyopod'
    finally:
        conn.close()


def test_migrate_schema_identity_no_op_on_empty_db(tmp_path):
    runtime = load_runtime_module()
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    try:
        # Fresh empty DB — neither table exists
        runtime._migrate_schema_identity(conn)
        conn.commit()
        # No tables created (this helper only renames; CREATE TABLE happens elsewhere)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = [row[0] for row in cur.fetchall()]
        assert 'relay_runtime' not in names
        assert 'daedalus_runtime' not in names
    finally:
        conn.close()
