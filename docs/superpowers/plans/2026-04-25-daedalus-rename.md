# Daedalus Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand the project from `hermes-relay` to **Daedalus** in a single clean sweep — no backward compatibility, no dual names, no deprecation cycle.

**Architecture:** Phased migration. Phase 1 builds new migration infrastructure additively (no break). Phase 2 switches path constants and env vars to the new identity (the migrator handles old data gracefully). Phases 3–4 rename Python identifiers and SQL schema mechanically. Phases 5–6 reshape the CLI surface and systemd units. Phases 7–9 handle plugin/asset/skill/docs renames, version bump, ADR, and grep audit.

**Tech Stack:** Python 3.11 (`/usr/bin/python3`), pytest, SQLite (WAL mode), systemd user services, argparse, importlib (dual-import pattern).

**Spec:** `docs/superpowers/specs/2026-04-25-daedalus-rename-design.md`

---

## Pre-flight context for implementer subagents

**Repo:** `/home/radxa/WS/hermes-relay`

**Test command:** Always use `/usr/bin/python3 -m pytest` (system Python 3.11 has pyyaml + jsonschema; homebrew python3 does not).

**Baseline:** 244 tests passing, 1 pre-existing failure in `tests/test_runtime_tools_alerts.py` (unrelated to this rename — leave the underlying failure alone, but path/identifier strings inside it still get renamed).

**Live workspace:** `/home/radxa/.hermes/workflows/yoyopod` — **do not** modify state files there during plan execution. The cutover (per spec Section 6) is a separate manual step after the plan lands.

**Dual-import pattern:** every plugin module has a relative-import `try` block with an `importlib.util.spec_from_file_location` fallback, used when modules are loaded as standalone scripts. Preserve this shape on every edit.

**`importlib.util.spec_from_file_location("<key>", path)` keys** are mostly cosmetic strings — they appear in stack traces but don't affect functionality. They still get renamed for consistency.

**Find-all-references safety:** before renaming an identifier, run a grep for the old name across the repo. Don't trust a single file's view.

```bash
grep -rn "<old_identifier>" --include="*.py" --include="*.md" --include="*.yaml"
```

---

## File structure overview

### Files modified

| File | Owns |
|---|---|
| `__init__.py` | Plugin entry point — `register_command(s)`, `register_skill`, `_load_local_module` |
| `schemas.py` | Argparse `setup_cli`, importlib spec key for `tools.py` |
| `tools.py` | Operator CLI dispatch (`execute_raw_args`, argparse subcommands), `RelayCommandError`, `_load_relay_module`, env vars, service profile constants, error literals, slash command handlers |
| `runtime.py` | SQLite schema (`init_relay_db`), event log (`append_relay_event`), `RELAY_SCHEMA_VERSION`, all engine logic |
| `alerts.py` | Outage alert decision; checks for `"relay error:"` literal |
| `scripts/install.py` | Plugin payload installer; `PLUGIN_NAME` constant |
| `workflows/code_review/paths.py` | Filesystem path constants for DB / event log / alert state / plugin entrypoint |
| `workflows/code_review/workspace.py` | Workspace factory; references plugin install path |
| `workflows/__main__.py` | Generic workflow dispatcher CLI; env var resolution |
| `plugin.yaml` | Plugin manifest — `name`, `description`, `version` |
| `assets/hermes-relay-icon.svg` | Icon SVG (rename file; visual stays) |
| `assets/hermes-relay-wordmark.svg` | Wordmark SVG (rename file + update embedded text) |
| `tests/*.py` | Many test files reference old identifiers/paths |
| `skills/<dir>/SKILL.md` | Operator/architecture skill docs — prose find-replace |
| `docs/*.md` | Architecture, operator cheat sheet, ADRs, README |
| `README.md` | Top-level README — prose find-replace |

### Files created

| File | Owns |
|---|---|
| `migration.py` | Filesystem migrator (`migrate_filesystem_state`) — renames `relay.db` + WAL/SHM sidecars, event log, alert state |
| `tests/test_daedalus_migration.py` | Tests for `migrate_filesystem_state` (4 cases) |
| `tests/test_daedalus_db_schema_migration.py` | Tests for `_migrate_schema_identity` SQL rename helper |
| `tests/test_systemd_template_units.py` | Tests for systemd template unit generation + install |
| `tests/test_workflow_slash_command.py` | Tests for `/workflow <name> <cmd>` dispatch |
| `docs/adr/ADR-0003-daedalus-rebrand.md` | ADR capturing the rename decision |

### Directories renamed

| Old | New |
|---|---|
| `~/.hermes/plugins/hermes-relay/` (install target) | `~/.hermes/plugins/daedalus/` |
| `skills/hermes-relay-architecture/` | `skills/daedalus-architecture/` |
| `skills/hermes-relay-hardening-slices/` | `skills/daedalus-hardening-slices/` |
| `skills/hermes-relay-model1-project-layout/` | `skills/daedalus-model1-project-layout/` |
| `skills/hermes-relay-retire-watchdog-and-migrate-control-schema/` | `skills/daedalus-retire-watchdog-and-migrate-control-schema/` |
| `skills/yoyopod-relay-alerts-monitoring/` | `skills/yoyopod-daedalus-alerts-monitoring/` |
| `skills/yoyopod-relay-outage-alerts/` | `skills/yoyopod-daedalus-outage-alerts/` |

---

# Phase 1 — Migration foundation (additive, no breakage)

The new migration helpers go in **first** so by the time later phases switch paths and identifiers, the system can already migrate old data into the new shape.

## Task 1.1: Filesystem migrator module

Build a new top-level module that owns startup-time filename migrations. Idempotent and safe whether or not old data exists.

**Files:**
- Create: `/home/radxa/WS/hermes-relay/migration.py`
- Create: `/home/radxa/WS/hermes-relay/tests/test_daedalus_migration.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_daedalus_migration.py`:

```python
import importlib.util
from pathlib import Path

import pytest


MIGRATION_MODULE_PATH = Path(__file__).resolve().parents[1] / "migration.py"


def load_migration_module():
    spec = importlib.util.spec_from_file_location("daedalus_migration_test", MIGRATION_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migrate_filesystem_state_no_op_on_clean_workflow_root(tmp_path):
    migration = load_migration_module()
    result = migration.migrate_filesystem_state(tmp_path)
    assert result == []


def test_migrate_filesystem_state_renames_db_and_sidecars(tmp_path):
    migration = load_migration_module()
    old_dir = tmp_path / "state" / "relay"
    old_dir.mkdir(parents=True)
    (old_dir / "relay.db").write_bytes(b"sqlite-data")
    (old_dir / "relay.db-wal").write_bytes(b"wal-data")
    (old_dir / "relay.db-shm").write_bytes(b"shm-data")

    result = migration.migrate_filesystem_state(tmp_path)

    new_dir = tmp_path / "state" / "daedalus"
    assert (new_dir / "daedalus.db").read_bytes() == b"sqlite-data"
    assert (new_dir / "daedalus.db-wal").read_bytes() == b"wal-data"
    assert (new_dir / "daedalus.db-shm").read_bytes() == b"shm-data"
    assert not (old_dir / "relay.db").exists()
    assert not (old_dir / "relay.db-wal").exists()
    assert not (old_dir / "relay.db-shm").exists()
    # Old empty dir gets removed
    assert not old_dir.exists()
    # Returns descriptions of what happened
    assert any("relay.db" in line and "daedalus.db" in line for line in result)


def test_migrate_filesystem_state_renames_event_log(tmp_path):
    migration = load_migration_module()
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "relay-events.jsonl").write_text("event-1\nevent-2\n", encoding="utf-8")

    result = migration.migrate_filesystem_state(tmp_path)

    assert (memory_dir / "daedalus-events.jsonl").read_text(encoding="utf-8") == "event-1\nevent-2\n"
    assert not (memory_dir / "relay-events.jsonl").exists()
    assert any("relay-events.jsonl" in line for line in result)


def test_migrate_filesystem_state_renames_alert_state(tmp_path):
    migration = load_migration_module()
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "hermes-relay-alert-state.json").write_text('{"k":"v"}', encoding="utf-8")

    result = migration.migrate_filesystem_state(tmp_path)

    assert (memory_dir / "daedalus-alert-state.json").read_text(encoding="utf-8") == '{"k":"v"}'
    assert not (memory_dir / "hermes-relay-alert-state.json").exists()
    assert any("hermes-relay-alert-state.json" in line for line in result)


def test_migrate_filesystem_state_idempotent_when_already_migrated(tmp_path):
    migration = load_migration_module()
    new_db_dir = tmp_path / "state" / "daedalus"
    new_db_dir.mkdir(parents=True)
    (new_db_dir / "daedalus.db").write_bytes(b"already-here")
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "daedalus-events.jsonl").write_text("kept", encoding="utf-8")

    result = migration.migrate_filesystem_state(tmp_path)

    # No move attempted because new files already exist; old files don't either
    assert result == []
    assert (new_db_dir / "daedalus.db").read_bytes() == b"already-here"


def test_migrate_filesystem_state_skips_old_when_new_present(tmp_path):
    """If both old and new exist, leave both untouched (manual operator
    inspection required). Conservative: never overwrite existing new files."""
    migration = load_migration_module()
    old_dir = tmp_path / "state" / "relay"
    old_dir.mkdir(parents=True)
    (old_dir / "relay.db").write_bytes(b"old-data")
    new_dir = tmp_path / "state" / "daedalus"
    new_dir.mkdir(parents=True)
    (new_dir / "daedalus.db").write_bytes(b"new-data")

    result = migration.migrate_filesystem_state(tmp_path)

    # No move; both files preserved as-is
    assert (old_dir / "relay.db").read_bytes() == b"old-data"
    assert (new_dir / "daedalus.db").read_bytes() == b"new-data"
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_daedalus_migration.py -v`
Expected: FAIL — `migration.py` does not exist; `ModuleNotFoundError` or similar.

- [ ] **Step 3: Implement `migration.py`**

Create `/home/radxa/WS/hermes-relay/migration.py`:

```python
"""Filesystem migration for the Daedalus rebrand.

Renames relay-era files to daedalus paths in a workflow root. Idempotent
and conservative: if a new-named file already exists, the matching old
file is left untouched (operator must inspect manually).
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _rename_if_only_old_exists(old: Path, new: Path) -> str | None:
    """Rename old → new only if old exists and new does not.

    Returns a human-readable description of the rename, or None if no
    action was taken.
    """
    if not old.exists():
        return None
    if new.exists():
        return None
    new.parent.mkdir(parents=True, exist_ok=True)
    old.rename(new)
    return f"renamed {old} -> {new}"


def migrate_filesystem_state(workflow_root: Path) -> list[str]:
    """Idempotent rename of relay-era paths to daedalus paths.

    Handles:
    - state/relay/relay.db (and SQLite WAL/SHM sidecars) -> state/daedalus/daedalus.db
    - memory/relay-events.jsonl -> memory/daedalus-events.jsonl
    - memory/hermes-relay-alert-state.json -> memory/daedalus-alert-state.json

    Removes the old state/relay/ directory if it ends up empty after
    the move.

    Returns a list of human-readable descriptions of renames performed.
    Empty list means no migration was needed (already in new shape, or
    workflow root has no relay-era data to migrate).
    """
    base = Path(workflow_root)
    descriptions: list[str] = []

    # SQLite DB triplet: main file + WAL + SHM. SQLite WAL mode requires
    # the sidecar filenames to match the main DB filename, so we move all
    # three together.
    old_state_dir = base / "state" / "relay"
    new_state_dir = base / "state" / "daedalus"
    sqlite_pairs: Iterable[tuple[Path, Path]] = (
        (old_state_dir / "relay.db", new_state_dir / "daedalus.db"),
        (old_state_dir / "relay.db-wal", new_state_dir / "daedalus.db-wal"),
        (old_state_dir / "relay.db-shm", new_state_dir / "daedalus.db-shm"),
    )
    for old, new in sqlite_pairs:
        desc = _rename_if_only_old_exists(old, new)
        if desc:
            descriptions.append(desc)

    # Event log and alert state files (single-file moves)
    memory_pairs: Iterable[tuple[Path, Path]] = (
        (base / "memory" / "relay-events.jsonl", base / "memory" / "daedalus-events.jsonl"),
        (
            base / "memory" / "hermes-relay-alert-state.json",
            base / "memory" / "daedalus-alert-state.json",
        ),
    )
    for old, new in memory_pairs:
        desc = _rename_if_only_old_exists(old, new)
        if desc:
            descriptions.append(desc)

    # If state/relay/ ended up empty, remove it
    if old_state_dir.exists() and old_state_dir.is_dir():
        try:
            next(old_state_dir.iterdir())
        except StopIteration:
            old_state_dir.rmdir()

    return descriptions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_daedalus_migration.py -v`
Expected: PASS — all 6 tests green.

- [ ] **Step 5: Commit**

```bash
git add migration.py tests/test_daedalus_migration.py
git commit -m "$(cat <<'EOF'
feat(migration): filesystem migrator for relay-era → daedalus paths

Idempotent rename of state/relay/relay.db (+ WAL/SHM sidecars),
memory/relay-events.jsonl, memory/hermes-relay-alert-state.json
to their daedalus equivalents. Skips when new file already exists
(no overwrite). Removes empty state/relay/ dir post-move.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 1.2: SQL schema identity migrator helper

Add a helper in `runtime.py` that, given an open SQLite connection, renames the `relay_runtime` table and updates the `runtime_id` row. Idempotent.

**Files:**
- Modify: `/home/radxa/WS/hermes-relay/runtime.py` (add `_migrate_schema_identity` near `init_relay_db`)
- Create: `/home/radxa/WS/hermes-relay/tests/test_daedalus_db_schema_migration.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_daedalus_db_schema_migration.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_daedalus_db_schema_migration.py -v`
Expected: FAIL — `_migrate_schema_identity` does not exist; `AttributeError`.

- [ ] **Step 3: Add `_migrate_schema_identity` to `runtime.py`**

In `runtime.py`, add this function above `def init_relay_db` (around line 180):

```python
def _migrate_schema_identity(conn) -> None:
    """Rename relay-era schema artifacts to daedalus equivalents.

    Idempotent: no-op on a fresh DB, no-op on an already-migrated DB.

    Operations performed when relay-era artifacts are detected:
    - ALTER TABLE relay_runtime RENAME TO daedalus_runtime
    - UPDATE daedalus_runtime SET runtime_id='daedalus' WHERE runtime_id='relay'

    Must be called before CREATE TABLE IF NOT EXISTS daedalus_runtime so
    the rename happens cleanly without producing two tables.
    """
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='relay_runtime'"
    )
    if cur.fetchone() is not None:
        conn.execute("ALTER TABLE relay_runtime RENAME TO daedalus_runtime")

    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daedalus_runtime'"
    )
    if cur.fetchone() is not None:
        conn.execute(
            "UPDATE daedalus_runtime SET runtime_id='daedalus' WHERE runtime_id='relay'"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_daedalus_db_schema_migration.py -v`
Expected: PASS — all 3 tests green.

- [ ] **Step 5: Commit**

```bash
git add runtime.py tests/test_daedalus_db_schema_migration.py
git commit -m "$(cat <<'EOF'
feat(runtime): add _migrate_schema_identity SQL rename helper

Idempotent ALTER TABLE relay_runtime -> daedalus_runtime plus
runtime_id row update. Will be wired into init_relay_db (to be
renamed init_daedalus_db) so existing DBs migrate transparently.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 1.3: Wire migrators into `init_relay_db`

The function still has its old name (renamed in Phase 3). What changes here is:
- Filesystem migration runs at the top
- SQL schema identity migration runs immediately after the DB connection opens
- Function signature changes: `db_path` → `workflow_root` (cleaner — function derives db_path internally via `runtime_paths`)

This is the single most subtle task in the plan because it changes a public-ish function signature. All callers update in the same commit.

**Files:**
- Modify: `/home/radxa/WS/hermes-relay/runtime.py` — `init_relay_db` signature + body
- Modify: `/home/radxa/WS/hermes-relay/runtime.py` — call sites at lines 563, 592, 674
- Modify: `/home/radxa/WS/hermes-relay/tools.py` — call site at line 1126
- Modify: `/home/radxa/WS/hermes-relay/tests/test_runtime_tools_alerts.py` — fixture updates

- [ ] **Step 1: Find all `init_relay_db` callers**

Run: `grep -rn "init_relay_db" --include="*.py" /home/radxa/WS/hermes-relay`
Expected: matches in `runtime.py` (definition + 3 call sites), `tools.py` (1 call site), test files.

- [ ] **Step 2: Add `workflow_root` import to runtime.py if not present**

Check that `runtime.py` imports `runtime_paths` from `workflows.code_review.paths`. Search for `from workflows.code_review.paths import`. If not present, add at module top:

```python
from workflows.code_review.paths import runtime_paths
```

- [ ] **Step 3: Modify `init_relay_db` signature and body in `runtime.py`**

Replace the existing `init_relay_db` definition (around line 182) with:

```python
def init_relay_db(*, workflow_root: Path, project_key: str) -> dict[str, Any]:
    # 1. Filesystem-level migration (renames relay-era files if present).
    #    Done before opening the DB so we don't open a stale empty file.
    try:
        from migration import migrate_filesystem_state
    except ImportError:
        # Standalone-script fallback (dual-import pattern).
        from importlib.util import spec_from_file_location, module_from_spec
        _migration_path = Path(__file__).resolve().parent / "migration.py"
        _spec = spec_from_file_location("daedalus_migration_for_runtime", _migration_path)
        _module = module_from_spec(_spec)
        _spec.loader.exec_module(_module)
        migrate_filesystem_state = _module.migrate_filesystem_state
    migrate_filesystem_state(workflow_root)

    # 2. Resolve canonical paths and open the DB.
    paths = runtime_paths(workflow_root)
    db_path = paths["db_path"]
    conn = _connect(db_path)
    try:
        # 3. SQL identity migration (rename relay_runtime -> daedalus_runtime
        #    if needed). Must run BEFORE the CREATE TABLE statements below.
        _migrate_schema_identity(conn)

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS relay_runtime (
              runtime_id TEXT PRIMARY KEY,
```

(Keep the rest of the executescript block as-is for now — Phase 4 renames the SQL table to `daedalus_runtime`.)

- [ ] **Step 4: Update `init_relay_db` callers in `runtime.py`**

Find the three call sites at lines 563, 592, 674 (line numbers may have shifted). Each currently looks like:

```python
init_relay_db(db_path=paths["db_path"], project_key="yoyopod")
```

Change each to use the workflow_root that's already in scope. Look at the surrounding code — most callers receive `workflow_root` as a parameter. For example:

```python
# Old
paths = runtime_paths(workflow_root)
init_relay_db(db_path=paths["db_path"], project_key="yoyopod")
# New
init_relay_db(workflow_root=workflow_root, project_key="yoyopod")
```

The `paths = runtime_paths(workflow_root)` call may still be needed for other path uses (event_log_path); leave that line alone if so. Only the `init_relay_db(...)` call changes.

- [ ] **Step 5: Update `init_relay_db` caller in `tools.py`**

Around line 1122-1126, the current code looks like:

```python
def cmd_init(...):
    paths = runtime_paths(workflow_root)
    relay = _load_relay_module(workflow_root)
    return relay.init_relay_db(db_path=paths["db_path"], project_key=args.project_key)
```

Change the last line to:

```python
    return relay.init_relay_db(workflow_root=workflow_root, project_key=args.project_key)
```

- [ ] **Step 6: Update test fixtures in `tests/test_runtime_tools_alerts.py`**

Around line 451 there's a fixture mocking `_runtime_paths`. The hardcoded paths reference `state/relay/relay.db` — leave the path strings alone for now (they're updated in Phase 2). The `init_relay_db` calls in this file (if any) need to switch to the new keyword arg `workflow_root` instead of `db_path`.

```bash
grep -n "init_relay_db" tests/test_runtime_tools_alerts.py
```

For each match, update the call to pass `workflow_root=...` instead of `db_path=...`. If a test passes a custom db_path, it should set up a workflow_root tmp_path and let runtime_paths derive the db_path.

- [ ] **Step 7: Run full test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -v 2>&1 | tail -30`
Expected: all 244 + 9 new tests from tasks 1.1 and 1.2 pass.

Then: `/usr/bin/python3 -m pytest tests/test_runtime_tools_alerts.py -v 2>&1 | tail -20`
Expected: pre-existing failure remains (unrelated to this rename); no NEW failures introduced.

- [ ] **Step 8: Commit**

```bash
git add runtime.py tools.py tests/test_runtime_tools_alerts.py
git commit -m "$(cat <<'EOF'
feat(runtime): wire migrators into init_relay_db

init_relay_db now takes workflow_root instead of db_path, derives
paths via runtime_paths, and runs the filesystem migrator + SQL
identity migrator before opening the DB. Pure forward path: existing
relay-era data migrates transparently on next runtime startup.

Function name still init_relay_db; renamed to init_daedalus_db in
Phase 3 alongside the broader identifier sweep.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 2 — Path constants and env vars

The migration foundation is in place. Now switch path constants to point at the daedalus filenames and rename env vars.

## Task 2.1: Switch path constants to daedalus filenames

**Files:**
- Modify: `/home/radxa/WS/hermes-relay/workflows/code_review/paths.py` — `runtime_paths` body
- Modify: `/home/radxa/WS/hermes-relay/tests/test_workflows_code_review_paths.py` — expected paths

- [ ] **Step 1: Find tests that assert path strings**

Run: `grep -n "relay.db\|relay-events\|hermes-relay-alert-state" tests/test_workflows_code_review_paths.py`
Expected: ~4-6 references in the test file.

- [ ] **Step 2: Update `runtime_paths` in `paths.py`**

In `workflows/code_review/paths.py`, find the `runtime_paths` function (around line 30):

```python
def runtime_paths(workflow_root: Path) -> dict[str, Path]:
    base_dir = runtime_base_dir(workflow_root)
    return {
        "db_path": base_dir / "state" / "relay" / "relay.db",
        "event_log_path": base_dir / "memory" / "relay-events.jsonl",
        "alert_state_path": base_dir / "memory" / "hermes-relay-alert-state.json",
    }
```

Change to:

```python
def runtime_paths(workflow_root: Path) -> dict[str, Path]:
    base_dir = runtime_base_dir(workflow_root)
    return {
        "db_path": base_dir / "state" / "daedalus" / "daedalus.db",
        "event_log_path": base_dir / "memory" / "daedalus-events.jsonl",
        "alert_state_path": base_dir / "memory" / "daedalus-alert-state.json",
    }
```

- [ ] **Step 3: Update `tests/test_workflows_code_review_paths.py`**

Find and replace path strings in the test file. The tests assert what `runtime_paths` returns:

```python
# Old assertions
assert paths["db_path"] == workflow_root / "runtime" / "state" / "relay" / "relay.db"
assert paths["event_log_path"] == workflow_root / "runtime" / "memory" / "relay-events.jsonl"
# (and similar without "runtime/" subdir)
```

Replace with:

```python
assert paths["db_path"] == workflow_root / "runtime" / "state" / "daedalus" / "daedalus.db"
assert paths["event_log_path"] == workflow_root / "runtime" / "memory" / "daedalus-events.jsonl"
# (and similar)
```

Also update any `alert_state_path` references from `"hermes-relay-alert-state.json"` to `"daedalus-alert-state.json"`.

- [ ] **Step 4: Update `tests/test_runtime_tools_alerts.py` path strings**

In `tests/test_runtime_tools_alerts.py`, the test fixture (around line 451) references the old paths in a `_runtime_paths` mock. Update:

```python
# Old
"db_path": workflow_root / "state" / "relay" / "relay.db",
"event_log_path": workflow_root / "memory" / "relay-events.jsonl",
# New
"db_path": workflow_root / "state" / "daedalus" / "daedalus.db",
"event_log_path": workflow_root / "memory" / "daedalus-events.jsonl",
```

Also update line 46:

```python
# Old
db_path = tmp_path / "relay.db"
# New
db_path = tmp_path / "daedalus.db"
```

- [ ] **Step 5: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/test_workflows_code_review_paths.py tests/test_workflows_code_review_workspace.py -v`
Expected: PASS.

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: 250 passed (244 original + 6 new from Task 1.1 + 3 new from Task 1.2 - 3 if some pre-existing tests broke; the count should be in that ballpark).

- [ ] **Step 6: Commit**

```bash
git add workflows/code_review/paths.py tests/test_workflows_code_review_paths.py tests/test_runtime_tools_alerts.py
git commit -m "$(cat <<'EOF'
feat(paths): switch runtime_paths to daedalus filenames

state/relay/relay.db -> state/daedalus/daedalus.db
memory/relay-events.jsonl -> memory/daedalus-events.jsonl
memory/hermes-relay-alert-state.json -> memory/daedalus-alert-state.json

Existing relay-era data migrates transparently via the migrator wired
into init_relay_db (Task 1.3).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.2: Rename environment variables

Replace `HERMES_RELAY_WORKFLOW_ROOT` and `YOYOPOD_RELAY_WORKFLOW_ROOT` with `DAEDALUS_WORKFLOW_ROOT` everywhere. Hard cut, no fallbacks.

**Files:**
- Modify: `/home/radxa/WS/hermes-relay/tools.py` (line ~21)
- Modify: `/home/radxa/WS/hermes-relay/alerts.py` (line ~15)
- Modify: `/home/radxa/WS/hermes-relay/workflows/code_review/paths.py` (line ~9)
- Modify: `/home/radxa/WS/hermes-relay/workflows/__main__.py` (line ~22)
- Modify: any tests that reference these env vars

- [ ] **Step 1: Find all references**

Run:

```bash
grep -rn "HERMES_RELAY_WORKFLOW_ROOT\|YOYOPOD_RELAY_WORKFLOW_ROOT\|RELAY_SYSTEMD_USER_DIR" --include="*.py" /home/radxa/WS/hermes-relay
```

Expected: 5-8 matches across `tools.py`, `alerts.py`, `paths.py`, `workflows/__main__.py`, and possibly a test or two.

- [ ] **Step 2: Update `workflows/code_review/paths.py`**

Find:

```python
DEFAULT_WORKFLOW_ROOT_ENV_VARS = ("YOYOPOD_RELAY_WORKFLOW_ROOT", "HERMES_RELAY_WORKFLOW_ROOT")
```

Replace with:

```python
DEFAULT_WORKFLOW_ROOT_ENV_VARS = ("DAEDALUS_WORKFLOW_ROOT",)
```

- [ ] **Step 3: Update `tools.py`**

Find (around line 21):

```python
DEFAULT_WORKFLOW_ROOT_ENV_VARS = ("YOYOPOD_RELAY_WORKFLOW_ROOT", "HERMES_RELAY_WORKFLOW_ROOT")
```

Replace with:

```python
DEFAULT_WORKFLOW_ROOT_ENV_VARS = ("DAEDALUS_WORKFLOW_ROOT",)
```

Also search in `tools.py` for any reference to `RELAY_SYSTEMD_USER_DIR` (likely in `_systemd_user_dir`):

```bash
grep -n "RELAY_SYSTEMD_USER_DIR" tools.py
```

Replace with `DAEDALUS_SYSTEMD_USER_DIR`.

- [ ] **Step 4: Update `alerts.py`**

Find (around line 15):

```python
DEFAULT_WORKFLOW_ROOT_ENV_VARS = ("YOYOPOD_RELAY_WORKFLOW_ROOT", "HERMES_RELAY_WORKFLOW_ROOT")
```

Replace with:

```python
DEFAULT_WORKFLOW_ROOT_ENV_VARS = ("DAEDALUS_WORKFLOW_ROOT",)
```

- [ ] **Step 5: Update `workflows/__main__.py`**

Find (around line 22):

```python
_WORKFLOW_ROOT_ENV_VARS = ("YOYOPOD_WORKFLOW_ROOT", "HERMES_RELAY_WORKFLOW_ROOT")
```

Replace with:

```python
_WORKFLOW_ROOT_ENV_VARS = ("DAEDALUS_WORKFLOW_ROOT", "YOYOPOD_WORKFLOW_ROOT")
```

(Per spec Section 4.7: `YOYOPOD_WORKFLOW_ROOT` is project-scoped and stays.)

Also update the docstring at top of file:

```python
# Old
If ``--workflow-root`` is omitted, the entrypoint honors these env vars
(first match wins): ``YOYOPOD_WORKFLOW_ROOT``, ``HERMES_RELAY_WORKFLOW_ROOT``.
# New
If ``--workflow-root`` is omitted, the entrypoint honors these env vars
(first match wins): ``DAEDALUS_WORKFLOW_ROOT``, ``YOYOPOD_WORKFLOW_ROOT``.
```

- [ ] **Step 6: Update tests that reference the env vars**

Run:

```bash
grep -rn "HERMES_RELAY_WORKFLOW_ROOT\|YOYOPOD_RELAY_WORKFLOW_ROOT" tests/
```

For each match, replace with `DAEDALUS_WORKFLOW_ROOT`. Examples typically look like:

```python
monkeypatch.setenv("HERMES_RELAY_WORKFLOW_ROOT", str(workflow_root))
# becomes
monkeypatch.setenv("DAEDALUS_WORKFLOW_ROOT", str(workflow_root))
```

- [ ] **Step 7: Run full test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: same number of tests passing as before (no regressions). Pre-existing failure in test_runtime_tools_alerts.py unchanged.

- [ ] **Step 8: Commit**

```bash
git add tools.py alerts.py workflows/code_review/paths.py workflows/__main__.py tests/
git commit -m "$(cat <<'EOF'
feat(env): rename HERMES_RELAY_WORKFLOW_ROOT -> DAEDALUS_WORKFLOW_ROOT

Hard cut. Drops YOYOPOD_RELAY_WORKFLOW_ROOT (was a project-prefixed
alias). RELAY_SYSTEMD_USER_DIR -> DAEDALUS_SYSTEMD_USER_DIR.

YOYOPOD_WORKFLOW_ROOT (project-scoped, no _RELAY_ infix) stays.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 3 — Python identifier renames

Mechanical renames of Python identifiers. Each task does one identifier across all references in one atomic commit. Tests stay green at every boundary.

## Task 3.1: Rename `RelayCommandError` → `DaedalusCommandError`

**Files:** All Python files referencing the class (definition in `tools.py`, catches in `alerts.py` and `tools.py` itself, possibly tests).

- [ ] **Step 1: Find all references**

```bash
grep -rn "RelayCommandError" --include="*.py" /home/radxa/WS/hermes-relay
```

Expected: ~6 references in `tools.py` (definition + multiple raises + 1 catch), possibly 0-1 in tests.

- [ ] **Step 2: Rename in `tools.py`**

In `tools.py`, find:

```python
class RelayCommandError(Exception):
    pass


class RelayArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise RelayCommandError(f"{message}\n\n{self.format_usage().strip()}")
```

Replace with:

```python
class DaedalusCommandError(Exception):
    pass


class DaedalusArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise DaedalusCommandError(f"{message}\n\n{self.format_usage().strip()}")
```

For all other `RelayCommandError` references in `tools.py` (raises and the single `except RelayCommandError as exc` near line 1406): replace with `DaedalusCommandError`.

For all `RelayArgumentParser` references in `tools.py`: replace with `DaedalusArgumentParser`.

- [ ] **Step 3: Update any other files**

Run:

```bash
grep -rn "RelayCommandError\|RelayArgumentParser" --include="*.py" /home/radxa/WS/hermes-relay
```

For each remaining match, replace with `DaedalusCommandError` / `DaedalusArgumentParser`.

- [ ] **Step 4: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS. No regressions.

- [ ] **Step 5: Commit**

```bash
git add tools.py
git commit -m "$(cat <<'EOF'
refactor: rename RelayCommandError -> DaedalusCommandError

Plus RelayArgumentParser -> DaedalusArgumentParser. All raises and
the single catch in tools.py updated atomically.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.2: Rename `_load_relay_module` → `_load_daedalus_module`

**Files:** `tools.py` (definition + ~10 callers), tests if referenced.

- [ ] **Step 1: Find all references**

```bash
grep -rn "_load_relay_module" --include="*.py" /home/radxa/WS/hermes-relay
```

Expected: ~10 references all in `tools.py`.

- [ ] **Step 2: Rename in `tools.py`**

In `tools.py`, find the function definition (around line 62):

```python
def _load_relay_module(workflow_root: Path):
    module_path = PLUGIN_DIR / "runtime.py"
    spec = importlib.util.spec_from_file_location("yoyopod_relay_plugin_runtime", module_path)
    if spec is None or spec.loader is None:
        raise DaedalusCommandError(f"unable to load Relay runtime from plugin package: {module_path}")
    ...
```

Replace with:

```python
def _load_daedalus_module(workflow_root: Path):
    module_path = PLUGIN_DIR / "runtime.py"
    spec = importlib.util.spec_from_file_location("daedalus_runtime", module_path)
    if spec is None or spec.loader is None:
        raise DaedalusCommandError(f"unable to load Daedalus runtime from plugin package: {module_path}")
    ...
```

(Note: also update the `spec_from_file_location` key from `"yoyopod_relay_plugin_runtime"` to `"daedalus_runtime"` and the error message from "Relay runtime" to "Daedalus runtime".)

- [ ] **Step 3: Update all callers in `tools.py`**

Search and replace all remaining `_load_relay_module(` with `_load_daedalus_module(`. Common patterns:

```python
relay = _load_relay_module(workflow_root)
# becomes (variable also renamed in Task 3.7)
relay = _load_daedalus_module(workflow_root)
```

For now, leave the variable name `relay` alone — Task 3.7 handles it.

- [ ] **Step 4: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools.py
git commit -m "$(cat <<'EOF'
refactor: rename _load_relay_module -> _load_daedalus_module

Also updates the importlib spec key from 'yoyopod_relay_plugin_runtime'
to 'daedalus_runtime' and the error message text.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.3: Rename `init_relay_db` → `init_daedalus_db`

**Files:** `runtime.py` (definition + 3 internal callers), `tools.py` (1 caller), tests.

- [ ] **Step 1: Find all references**

```bash
grep -rn "init_relay_db" --include="*.py" /home/radxa/WS/hermes-relay
```

Expected: ~5 references.

- [ ] **Step 2: Rename definition in `runtime.py`**

Find:

```python
def init_relay_db(*, workflow_root: Path, project_key: str) -> dict[str, Any]:
```

Replace with:

```python
def init_daedalus_db(*, workflow_root: Path, project_key: str) -> dict[str, Any]:
```

- [ ] **Step 3: Update internal callers in `runtime.py`**

Replace all `init_relay_db(...)` calls with `init_daedalus_db(...)`. Look for ~3 call sites (lines 563, 592, 674 in the original — line numbers may have shifted).

- [ ] **Step 4: Update caller in `tools.py`**

Find (around line 1126):

```python
return relay.init_relay_db(workflow_root=workflow_root, project_key=args.project_key)
```

Replace with:

```python
return relay.init_daedalus_db(workflow_root=workflow_root, project_key=args.project_key)
```

(The `relay` variable name is renamed in Task 3.7.)

- [ ] **Step 5: Update tests**

```bash
grep -rn "init_relay_db" tests/
```

For each match, replace with `init_daedalus_db`.

- [ ] **Step 6: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

Then run the unrelated-failure test file to confirm no NEW failures:
Run: `/usr/bin/python3 -m pytest tests/test_runtime_tools_alerts.py -q 2>&1 | tail -10`
Expected: pre-existing failure persists; no new failures.

- [ ] **Step 7: Commit**

```bash
git add runtime.py tools.py tests/
git commit -m "$(cat <<'EOF'
refactor: rename init_relay_db -> init_daedalus_db

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.4: Rename `append_relay_event` → `append_daedalus_event`

**Files:** `runtime.py` (definition + ~17 callers), tests.

- [ ] **Step 1: Find all references**

```bash
grep -rn "append_relay_event" --include="*.py" /home/radxa/WS/hermes-relay
```

Expected: ~17 references all in `runtime.py`, possibly 1-2 in tests.

- [ ] **Step 2: Rename definition in `runtime.py`**

Find (around line 459):

```python
def append_relay_event(*, event_log_path: Path, event: dict[str, Any]) -> dict[str, Any]:
```

Replace with:

```python
def append_daedalus_event(*, event_log_path: Path, event: dict[str, Any]) -> dict[str, Any]:
```

- [ ] **Step 3: Update all internal callers in `runtime.py`**

Use sed-style replace for all remaining occurrences:

```bash
grep -n "append_relay_event" runtime.py
```

For each match, replace `append_relay_event` with `append_daedalus_event`. The implementer should use Edit tool with `replace_all: true`.

- [ ] **Step 4: Update tests**

```bash
grep -rn "append_relay_event" tests/
```

For each match, replace with `append_daedalus_event`.

- [ ] **Step 5: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add runtime.py tests/
git commit -m "$(cat <<'EOF'
refactor: rename append_relay_event -> append_daedalus_event

17 call sites across runtime.py + test references updated atomically.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.5: Rename `RELAY_SCHEMA_VERSION` → `DAEDALUS_SCHEMA_VERSION`

**Files:** `runtime.py` (definition + ~5 references), tests if referenced.

- [ ] **Step 1: Find all references**

```bash
grep -rn "RELAY_SCHEMA_VERSION" --include="*.py" /home/radxa/WS/hermes-relay
```

Expected: ~5 references in `runtime.py`, possibly 0-1 in tests.

- [ ] **Step 2: Rename in `runtime.py`**

Use Edit with `replace_all: true` to replace all `RELAY_SCHEMA_VERSION` with `DAEDALUS_SCHEMA_VERSION`.

- [ ] **Step 3: Update tests if any**

```bash
grep -rn "RELAY_SCHEMA_VERSION" tests/
```

For each match, replace.

- [ ] **Step 4: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runtime.py tests/
git commit -m "$(cat <<'EOF'
refactor: rename RELAY_SCHEMA_VERSION -> DAEDALUS_SCHEMA_VERSION

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.6: Rename `_load_legacy_workflow_module` references and importlib spec keys

This task handles smaller, more scattered identifier rename: the importlib spec key prefix `hermes_relay_*` → `daedalus_*` everywhere.

**Files:** `__init__.py`, `schemas.py`, `scripts/install.py`, `alerts.py`, `tools.py`, `workflows/code_review/workspace.py`, all test files.

- [ ] **Step 1: Find all importlib spec keys with the old prefix**

```bash
grep -rn "spec_from_file_location.*hermes_relay" --include="*.py" /home/radxa/WS/hermes-relay
grep -rn "spec_from_file_location.*yoyopod_relay" --include="*.py" /home/radxa/WS/hermes-relay
```

Expected: many — ~50 references across tests, plus a few in production files.

- [ ] **Step 2: Mechanical rename — production files first**

For each of these production files, rename `hermes_relay_` to `daedalus_` and `yoyopod_relay_plugin_` to `daedalus_` in importlib spec keys:

- `__init__.py` — `f"hermes_relay_{module_name}"` → `f"daedalus_{module_name}"`
- `schemas.py` — `"hermes_relay_tools_for_schemas"` → `"daedalus_tools_for_schemas"`
- `scripts/install.py` — `"hermes_relay_install"` → `"daedalus_install"`
- `alerts.py` — `"yoyopod_relay_plugin_tools_for_alerts"` → `"daedalus_tools_for_alerts"`
- `workflows/code_review/workspace.py` — `f"hermes_relay_code_review_{name}"` → `f"daedalus_code_review_{name}"`

Use the Edit tool for each file. Verify with grep after each edit.

- [ ] **Step 3: Mechanical rename — test files**

Test files use `hermes_relay_*` prefix in their `load_module()` helpers. Use a single-shot rename approach:

```bash
# In each test file, run an Edit with replace_all=true to swap the prefix.
# Files to touch:
ls tests/test_*.py | xargs grep -l "hermes_relay" | sort -u
```

For each listed file, use Edit with `old_string: "hermes_relay_"` and `new_string: "daedalus_"` and `replace_all: true`.

Tests/files specifically affected (per the pre-task survey, ~14 files):
- `tests/test_install.py`
- `tests/test_runtime_tools_alerts.py`
- `tests/test_workflows_code_review_workspace.py` (~14 occurrences)
- `tests/test_workflows_code_review_entrypoint.py` (~6 occurrences)
- `tests/test_workflows_code_review_stale_lane.py` (~2 occurrences)
- `tests/test_workflows_code_review_session_runtime.py` (~8 occurrences)
- `tests/test_workflows_code_review_prompts.py` (~5 occurrences)
- `tests/test_workflows_code_review_cli.py` (~1 occurrence)
- `tests/test_workflows_code_review_reviews.py` (~5 occurrences)
- `tests/test_workflows_code_review_actions.py`
- `tests/test_workflows_code_review_health.py`
- `tests/test_workflows_code_review_paths.py`
- `tests/test_workflows_code_review_sessions.py`
- `tests/test_workflows_code_review_workflow.py`
- `tests/test_workflows_code_review_tools_bridge.py`
- `tests/test_workflows_code_review_adapter_status.py`
- `tests/test_workflows_code_review_github.py`

- [ ] **Step 4: Verify no `hermes_relay_` strings remain**

```bash
grep -rn "hermes_relay_" --include="*.py" /home/radxa/WS/hermes-relay
```

Expected: zero matches (in `*.py`; markdown docs are renamed in Phase 8).

- [ ] **Step 5: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: rename importlib spec keys hermes_relay_* -> daedalus_*

Plus yoyopod_relay_plugin_runtime -> daedalus_runtime,
yoyopod_relay_plugin_tools_for_alerts -> daedalus_tools_for_alerts.
~50 occurrences across production code and tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.7: Rename local variable `relay = _load_daedalus_module(...)` → `daedalus = ...`

Cleanup pass for local variable names. Boil-the-ocean cleanness — the variable holding the module reference should match the module name.

**Files:** `tools.py` (~10 call sites).

- [ ] **Step 1: Find all references**

```bash
grep -n "^[[:space:]]*relay = _load_daedalus_module\|^[[:space:]]*relay\." tools.py | head -30
```

The pattern to find is `relay = _load_daedalus_module(workflow_root)` and subsequent `relay.<member>` calls within the same function.

- [ ] **Step 2: Rename within `tools.py`**

For each function that loads the module, rename the local variable from `relay` to `daedalus`. This is safe because it's a function-local rename.

The cleanest approach: use Edit with `replace_all: false` on each occurrence with surrounding context. Examples:

```python
# Old
def cmd_status(...):
    relay = _load_daedalus_module(workflow_root)
    return relay.build_status(...)

# New
def cmd_status(...):
    daedalus = _load_daedalus_module(workflow_root)
    return daedalus.build_status(...)
```

Search pattern: each function in `tools.py` that calls `_load_daedalus_module` typically uses `relay.<x>` afterwards. Replace both the assignment and subsequent member accesses within that function.

For efficiency, the implementer can do a `replace_all=true` swap in a single Edit if the variable name `relay` appears nowhere else. Verify first:

```bash
grep -n "\brelay\b" tools.py | grep -v "_load_daedalus_module\|relay\."
```

If the only other matches are inside string literals (which Phase 3.8 handles separately) or comments, the wholesale rename is safe.

**Recommended:** use Edit per-function with surrounding context to avoid over-replacing.

- [ ] **Step 3: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tools.py
git commit -m "$(cat <<'EOF'
refactor: rename local variable relay -> daedalus

Function-local variable holding the module reference now matches
the module's identity. ~10 call sites in tools.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 4 — SQL schema and event log identifier renames

## Task 4.1: Rename SQL table `relay_runtime` → `daedalus_runtime`

**Files:** `runtime.py` (~10 references in CREATE/SELECT/UPDATE statements), tests.

- [ ] **Step 1: Find all references**

```bash
grep -n "relay_runtime" runtime.py
grep -rn "relay_runtime" --include="*.py" tests/
```

Expected: ~10 in `runtime.py`, 1-2 in tests.

- [ ] **Step 2: Rename in `runtime.py`**

Use Edit with `replace_all: true` on `runtime.py`:
- `old_string: "relay_runtime"`
- `new_string: "daedalus_runtime"`

This safely renames all references including:
- `CREATE TABLE IF NOT EXISTS relay_runtime` → `CREATE TABLE IF NOT EXISTS daedalus_runtime`
- All `SELECT * FROM relay_runtime` → `SELECT * FROM daedalus_runtime`
- All `UPDATE relay_runtime SET ...` → `UPDATE daedalus_runtime SET ...`
- `INSERT INTO relay_runtime` → `INSERT INTO daedalus_runtime`

- [ ] **Step 3: Update test references**

```bash
grep -rn "relay_runtime" tests/
```

For each match (most likely `tests/test_runtime_tools_alerts.py:77`), replace with `daedalus_runtime`.

- [ ] **Step 4: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS. The new test from Task 1.2 (`test_daedalus_db_schema_migration.py`) verifies the migration helper still works.

- [ ] **Step 5: Commit**

```bash
git add runtime.py tests/
git commit -m "$(cat <<'EOF'
refactor: rename SQL table relay_runtime -> daedalus_runtime

CREATE TABLE, SELECT, UPDATE, INSERT all switch atomically. The
identity migration helper added in Task 1.2 ensures existing DBs
with the old table name get renamed transparently on init.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4.2: Rename `runtime_id` literal `'relay'` → `'daedalus'` and instance ID defaults

**Files:** `runtime.py` (3 places: SELECT WHERE clause, UPDATE, INSERT VALUES).

- [ ] **Step 1: Find all `runtime_id='relay'` references**

```bash
grep -n "runtime_id='relay'\|runtime_id = 'relay'\|'relay-shadow-v1'\|'relay-active-v1'\|relay-plugin\|relay-shadow-service-1\|relay-active-service-1" runtime.py tools.py
```

Expected: ~6-8 string literal references.

- [ ] **Step 2: Rename in `runtime.py`**

Find each of these patterns and replace:

```python
# 1. SELECT clause (around line 391)
"SELECT schema_version FROM daedalus_runtime WHERE runtime_id='relay'"
# becomes
"SELECT schema_version FROM daedalus_runtime WHERE runtime_id='daedalus'"

# 2. INSERT VALUES (around line 397+)
INSERT INTO daedalus_runtime (
    runtime_id, ...
) VALUES (
    "relay-shadow-v1", ...  # or "relay-active-v1"
)
# becomes
INSERT INTO daedalus_runtime (
    runtime_id, ...
) VALUES (
    "daedalus-shadow-v1", ...  # or "daedalus-active-v1"
)

# 3. WHERE clauses with runtime_id='relay' (other UPDATEs, lines 696, 1758, 3000, 3190, 3277)
# Each becomes runtime_id='daedalus'
```

The implementer should grep for each old literal and replace with the new one.

- [ ] **Step 3: Update `tools.py` instance ID defaults**

Find:

```python
DEFAULT_INSTANCE_ID = "relay-plugin"
```

Replace with:

```python
DEFAULT_INSTANCE_ID = "daedalus-plugin"
```

(The shadow/active service instance IDs are renamed in Phase 6 — Task 6.1 — when systemd templates land.)

- [ ] **Step 4: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runtime.py tools.py
git commit -m "$(cat <<'EOF'
refactor: rename runtime_id 'relay' -> 'daedalus' and instance defaults

SELECT/UPDATE/INSERT statements that reference the runtime_id row
identity now use 'daedalus'. INSERT VALUES default
"relay-{shadow,active}-v1" -> "daedalus-{shadow,active}-v1".
DEFAULT_INSTANCE_ID "relay-plugin" -> "daedalus-plugin".

The Task 1.2 SQL migrator updates existing rows from 'relay' to
'daedalus' on init, so live data migrates transparently.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4.3: Rename event types `relay_runtime_*` → `daedalus_runtime_*`

**Files:** `runtime.py` (~6 references in event_id, event_type, dedupe_key strings).

- [ ] **Step 1: Find all references**

```bash
grep -n "relay_runtime_started\|relay_runtime_heartbeat\|evt:relay_runtime\|dedupe_key.*relay_runtime" runtime.py
```

Expected: ~6 references — both event types appear in event_id, event_type, and dedupe_key fields.

- [ ] **Step 2: Replace in `runtime.py`**

Use Edit with `replace_all: true`:
- `old_string: "relay_runtime_started"` → `new_string: "daedalus_runtime_started"`
- `old_string: "relay_runtime_heartbeat"` → `new_string: "daedalus_runtime_heartbeat"`
- `old_string: "evt:relay_runtime"` → `new_string: "evt:daedalus_runtime"`

After all three replaces, verify:

```bash
grep -n "relay_runtime" runtime.py
```

Expected: zero matches (the SQL table was renamed in Task 4.1 already).

- [ ] **Step 3: Update tests if referenced**

```bash
grep -rn "relay_runtime_started\|relay_runtime_heartbeat\|evt:relay_runtime" tests/
```

For each match, replace.

- [ ] **Step 4: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runtime.py tests/
git commit -m "$(cat <<'EOF'
refactor: rename event types relay_runtime_* -> daedalus_runtime_*

Engine-level events relay_runtime_started, relay_runtime_heartbeat
plus their event_id/dedupe_key prefixes. Lane/action/review event
types unchanged (they describe the workflow domain, not the engine).

Pre-cutover historical events on the live machine remain untouched
in the migrated daedalus-events.jsonl (append-only audit log).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 5 — CLI surface

## Task 5.1: Rename argparse `relay_command` dest and inner string literals

**Files:** `tools.py` (argparse dest declaration, error formatters), tests if referenced.

- [ ] **Step 1: Find all references**

```bash
grep -n "args\.relay_command\|relay_command\|dest=\"relay_command\"\|dest='relay_command'" tools.py
```

Expected: 3-4 references.

- [ ] **Step 2: Replace in `tools.py`**

Find the argparse declaration (likely in `configure_subcommands`):

```python
sub = parser.add_subparsers(dest="relay_command")
```

Replace with:

```python
sub = parser.add_subparsers(dest="daedalus_command")
```

Also find error formatters near line 1237 and 1407:

```python
raise DaedalusCommandError(f"unknown relay command: {args.relay_command}")
# becomes
raise DaedalusCommandError(f"unknown daedalus command: {args.daedalus_command}")
```

And the catch-block formatters near line 1406-1412:

```python
except DaedalusCommandError as exc:
    return f"relay error: {exc}"
...
return f"relay error: {detail or parser.format_usage().strip()}"
return f"relay error: unexpected {type(exc).__name__}: {exc}"
```

Replace all three `f"relay error: ...` with `f"daedalus error: ...`.

- [ ] **Step 3: Update `alerts.py` "relay error:" check**

In `alerts.py` around line 39:

```python
if result.startswith("relay error:"):
```

Replace with:

```python
if result.startswith("daedalus error:"):
```

- [ ] **Step 4: Update any tests that assert on "relay error:" prefix**

```bash
grep -rn "relay error:" tests/
```

For each match, replace with `daedalus error:`.

- [ ] **Step 5: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools.py alerts.py tests/
git commit -m "$(cat <<'EOF'
refactor: rename argparse relay_command -> daedalus_command + error literals

args.relay_command -> args.daedalus_command throughout.
"relay error:" prefix on user-facing error messages -> "daedalus error:".
alerts.py prefix check updated atomically.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5.2: Update `tools.py` argparse help texts and other prose strings

**Files:** `tools.py` (argparse help= and description= strings throughout).

- [ ] **Step 1: Find all "Relay" / "YoYoPod Relay" prose strings**

```bash
grep -n "YoYoPod Relay\|Hermes Relay\|the Relay\|Relay runtime\|Relay project" tools.py
```

Expected: many — argparse help texts, descriptions, error messages.

- [ ] **Step 2: Replace prose mechanically**

Use Edit with `replace_all: true` on `tools.py`:

```
old_string: "YoYoPod Relay"  ->  new_string: "Daedalus"
old_string: "Hermes Relay"   ->  new_string: "Daedalus"
old_string: "Relay runtime"  ->  new_string: "Daedalus runtime"
```

After each replace, run `grep -n "Relay" tools.py` to verify which references remain (some may need contextual replacement rather than mechanical).

The "Relay" word as a noun should generally become "Daedalus" or "Daedalus runtime" depending on context.

- [ ] **Step 3: Update specific error messages**

Find the argparse error-equivalent message:

```python
raise DaedalusCommandError("Relay runtime is not initialized; run `relay start` first")
```

Replace with:

```python
raise DaedalusCommandError("Daedalus runtime is not initialized; run `daedalus start` first")
```

- [ ] **Step 4: Verify no stray "Relay" remains in tools.py**

```bash
grep -n "\bRelay\b\|\brelay\b" tools.py
```

Remaining matches should be:
- The class name `DaedalusArgumentParser` (no "relay" anymore)
- Any other matches need context-specific replacement

- [ ] **Step 5: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools.py
git commit -m "$(cat <<'EOF'
refactor: rename argparse help/description prose Relay -> Daedalus

tools.py argparse help texts, command descriptions, and error
messages now read "Daedalus" instead of "Hermes Relay" / "YoYoPod
Relay" / "the Relay".

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5.3: Update `__init__.py` slash command registration to `/daedalus`

**Files:** `__init__.py`.

- [ ] **Step 1: Inspect current state**

Read `__init__.py`. The current `register(ctx)` function registers `"relay"` as both a slash command and CLI command.

- [ ] **Step 2: Replace `register(ctx)`**

Replace the entire `register(ctx)` function in `__init__.py` with:

```python
def register(ctx):
    ctx.register_command(
        "daedalus",
        execute_raw_args,
        description="Operate the Daedalus workflow engine from the current Hermes session.",
    )
    ctx.register_cli_command(
        name="daedalus",
        help="Operate the Daedalus workflow engine.",
        setup_fn=setup_cli,
        description="Daedalus workflow engine control surface.",
    )

    skill_md = PLUGIN_DIR / "skills" / "operator" / "SKILL.md"
    if skill_md.exists():
        ctx.register_skill("operator", skill_md, description="Operate the Daedalus engine.")
```

- [ ] **Step 3: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS. (Test suite doesn't test the actual Hermes ctx registration, so this is purely a code change.)

- [ ] **Step 4: Commit**

```bash
git add __init__.py
git commit -m "$(cat <<'EOF'
feat(slash): rename /relay -> /daedalus in plugin registration

ctx.register_command name + description, ctx.register_cli_command
name/help/description, ctx.register_skill description all updated
to reference Daedalus.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5.4: Add `/workflow <name> <cmd>` slash command

New slash command that lets the operator invoke any installed workflow's CLI without typing the full Python invocation.

**Files:**
- Modify: `/home/radxa/WS/hermes-relay/__init__.py` (register the new command)
- Modify: `/home/radxa/WS/hermes-relay/tools.py` (add `execute_workflow_command` handler)
- Create: `/home/radxa/WS/hermes-relay/tests/test_workflow_slash_command.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_workflow_slash_command.py`:

```python
import importlib.util
from pathlib import Path

import pytest


TOOLS_PATH = Path(__file__).resolve().parents[1] / "tools.py"


def load_tools():
    spec = importlib.util.spec_from_file_location("daedalus_tools_for_workflow_test", TOOLS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_execute_workflow_command_lists_workflows_with_no_args(tmp_path, monkeypatch):
    tools = load_tools()
    # Tools resolves workflow_root via env var; point it at tmp_path with a config
    workflow_root = tmp_path
    (workflow_root / "config").mkdir()
    (workflow_root / "config" / "workflow.yaml").write_text(
        "workflow:\n  name: code-review\n  schema-version: 1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DAEDALUS_WORKFLOW_ROOT", str(workflow_root))

    result = tools.execute_workflow_command("")
    assert "available workflows" in result.lower()
    assert "code-review" in result


def test_execute_workflow_command_routes_to_workflow_cli(tmp_path, monkeypatch):
    tools = load_tools()
    workflow_root = tmp_path
    (workflow_root / "config").mkdir()
    (workflow_root / "config" / "workflow.yaml").write_text(
        "workflow:\n  name: code-review\n  schema-version: 1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DAEDALUS_WORKFLOW_ROOT", str(workflow_root))

    # Stub run_cli so we can assert how it was called
    captured: dict = {}
    def fake_run_cli(workflow_root_arg, argv, *, require_workflow=None):
        captured["workflow_root"] = workflow_root_arg
        captured["argv"] = argv
        captured["require_workflow"] = require_workflow
        return 0

    monkeypatch.setattr("workflows.run_cli", fake_run_cli)

    result = tools.execute_workflow_command("code-review status --json")

    assert captured["require_workflow"] == "code-review"
    assert captured["argv"] == ["status", "--json"]
    assert isinstance(result, str)


def test_execute_workflow_command_rejects_unknown_workflow_name(tmp_path, monkeypatch):
    tools = load_tools()
    workflow_root = tmp_path
    (workflow_root / "config").mkdir()
    (workflow_root / "config" / "workflow.yaml").write_text(
        "workflow:\n  name: code-review\n  schema-version: 1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DAEDALUS_WORKFLOW_ROOT", str(workflow_root))

    result = tools.execute_workflow_command("nonexistent-workflow status")
    assert "daedalus error" in result.lower() or "unknown workflow" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_workflow_slash_command.py -v`
Expected: FAIL — `execute_workflow_command` does not exist; `AttributeError`.

- [ ] **Step 3: Add `execute_workflow_command` handler in `tools.py`**

In `tools.py`, near the `execute_raw_args` function, add:

```python
def execute_workflow_command(raw_args: str) -> str:
    """Slash command handler for /workflow <name> <cmd> [args].

    Bare invocation (no args): lists available workflows under workflows/.
    Single arg (workflow name): shows that workflow's --help.
    Full invocation: routes through workflows.run_cli with require_workflow.
    """
    workflow_root = DEFAULT_WORKFLOW_ROOT  # honors DAEDALUS_WORKFLOW_ROOT env via paths.py
    parts = raw_args.strip().split()

    if not parts:
        # List installed workflows
        try:
            from workflows import list_workflows
        except ImportError:
            from importlib.util import spec_from_file_location, module_from_spec
            _wfpath = PLUGIN_DIR / "workflows" / "__init__.py"
            _spec = spec_from_file_location("daedalus_workflows", _wfpath)
            _module = module_from_spec(_spec)
            _spec.loader.exec_module(_module)
            list_workflows = _module.list_workflows
        names = list_workflows()
        return "available workflows: " + ", ".join(names) if names else "no workflows installed"

    name, *cmd_args = parts

    try:
        from workflows import run_cli
    except ImportError:
        from importlib.util import spec_from_file_location, module_from_spec
        _wfpath = PLUGIN_DIR / "workflows" / "__init__.py"
        _spec = spec_from_file_location("daedalus_workflows", _wfpath)
        _module = module_from_spec(_spec)
        _spec.loader.exec_module(_module)
        run_cli = _module.run_cli

    try:
        if not cmd_args:
            cmd_args = ["--help"]
        rc = run_cli(workflow_root, cmd_args, require_workflow=name)
        return f"workflow '{name}' exited with status {rc}" if rc != 0 else "ok"
    except Exception as exc:
        return f"daedalus error: {exc}"
```

- [ ] **Step 4: Add `list_workflows` to `workflows/__init__.py` if it doesn't exist**

In `workflows/__init__.py`, add at the bottom:

```python
def list_workflows() -> list[str]:
    """Return canonical names of installed workflows.

    Scans the `workflows/` package directory for sub-packages that declare
    the workflow-plugin contract (have a NAME attribute).
    """
    pkg_dir = Path(__file__).parent
    names: list[str] = []
    for entry in sorted(pkg_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        init_file = entry / "__init__.py"
        if not init_file.exists():
            continue
        try:
            module = load_workflow(entry.name.replace("_", "-"))
            if hasattr(module, "NAME"):
                names.append(module.NAME)
        except Exception:
            continue
    return names
```

- [ ] **Step 5: Register `/workflow` in `__init__.py`**

In `__init__.py`, add inside `register(ctx)`:

```python
def register(ctx):
    ctx.register_command(
        "daedalus",
        execute_raw_args,
        description="Operate the Daedalus workflow engine from the current Hermes session.",
    )
    ctx.register_command(
        "workflow",
        execute_workflow_command,
        description="Run a workflow's CLI (e.g. /workflow code-review status).",
    )
    ctx.register_cli_command(
        name="daedalus",
        help="Operate the Daedalus workflow engine.",
        setup_fn=setup_cli,
        description="Daedalus workflow engine control surface.",
    )
    ...
```

Also update the import block at the top of `__init__.py` to include `execute_workflow_command`:

```python
try:
    from .schemas import setup_cli
    from .tools import execute_raw_args, execute_workflow_command
except ImportError:
    def _load_local_module(module_name: str):
        ...
    setup_cli = _load_local_module("schemas").setup_cli
    execute_raw_args = _load_local_module("tools").execute_raw_args
    execute_workflow_command = _load_local_module("tools").execute_workflow_command
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_workflow_slash_command.py -v`
Expected: PASS — all 3 tests green.

Run full suite: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add __init__.py tools.py workflows/__init__.py tests/test_workflow_slash_command.py
git commit -m "$(cat <<'EOF'
feat(slash): /workflow <name> <cmd> command

New top-level slash command routes to workflows.run_cli with
require_workflow=name. Bare /workflow lists available workflows.
With name only, prints --help. Errors prefix with 'daedalus error:'.

Adds list_workflows() helper to workflows/__init__.py for
introspection-based listing of installed workflow packages.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5.5: Add `daedalus migrate-filesystem` CLI subcommand

**Files:** `tools.py` (new argparse subcommand + dispatch), test in existing test file or new one.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_daedalus_migration.py`:

```python
def test_cli_migrate_filesystem_invokes_migrator(tmp_path, monkeypatch):
    """Smoke test: `daedalus migrate-filesystem --workflow-root <path>`
    invokes migrate_filesystem_state and prints the result."""
    import importlib.util
    tools_path = Path(__file__).resolve().parents[1] / "tools.py"
    spec = importlib.util.spec_from_file_location("daedalus_tools_for_migrate_test", tools_path)
    tools = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tools)

    # Seed an old-shape workflow
    old_dir = tmp_path / "state" / "relay"
    old_dir.mkdir(parents=True)
    (old_dir / "relay.db").write_bytes(b"data")

    result = tools.execute_raw_args(f"migrate-filesystem --workflow-root {tmp_path}")

    # Should not be an error, and should report the migration
    assert "daedalus error" not in result.lower()
    assert "renamed" in result.lower() or "migrated" in result.lower()
    assert (tmp_path / "state" / "daedalus" / "daedalus.db").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/usr/bin/python3 -m pytest tests/test_daedalus_migration.py::test_cli_migrate_filesystem_invokes_migrator -v`
Expected: FAIL — argparse rejects `migrate-filesystem` as an unknown command.

- [ ] **Step 3: Add the subcommand in `tools.py`**

In `tools.py::configure_subcommands`, add a new subparser:

```python
def configure_subcommands(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="daedalus_command")
    ...
    # Existing subcommands ...

    migrate_fs_cmd = sub.add_parser(
        "migrate-filesystem",
        help="Migrate relay-era filesystem paths to daedalus paths.",
    )
    migrate_fs_cmd.add_argument(
        "--workflow-root",
        type=Path,
        default=DEFAULT_WORKFLOW_ROOT,
        help="Workflow root to migrate (default: %(default)s)",
    )
    migrate_fs_cmd.set_defaults(handler=cmd_migrate_filesystem)
```

Add the handler function in `tools.py`:

```python
def cmd_migrate_filesystem(args, parser) -> str:
    """Run the filesystem migrator for the given workflow root."""
    try:
        from migration import migrate_filesystem_state
    except ImportError:
        import importlib.util
        _path = PLUGIN_DIR / "migration.py"
        _spec = importlib.util.spec_from_file_location("daedalus_migration_for_cli", _path)
        _module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_module)
        migrate_filesystem_state = _module.migrate_filesystem_state

    workflow_root = args.workflow_root
    descriptions = migrate_filesystem_state(workflow_root)
    if not descriptions:
        return f"no migration needed (workflow_root={workflow_root})"
    lines = [f"migrated filesystem state under {workflow_root}:"]
    lines.extend(f"  - {d}" for d in descriptions)
    return "\n".join(lines)
```

- [ ] **Step 4: Wire `cmd_migrate_filesystem` into the dispatch**

In `tools.py::execute_raw_args`, locate the `args.daedalus_command` dispatch (likely a `match` or `if/elif` chain or `args.handler(args, parser)`). If using a handler-based dispatch (set via `set_defaults(handler=...)`), the new subcommand routes automatically.

If using a hardcoded `if/elif`, add:

```python
if args.daedalus_command == "migrate-filesystem":
    return cmd_migrate_filesystem(args, parser)
```

- [ ] **Step 5: Add a top-level `__main__` block to `tools.py`**

So operators can run the migrators directly from a shell during cutover (without needing a Hermes session), append to the bottom of `tools.py`:

```python
if __name__ == "__main__":
    import sys
    result = execute_raw_args(" ".join(sys.argv[1:]))
    print(result)
    sys.exit(0 if not result.startswith("daedalus error:") else 1)
```

This means: `python3 ~/.hermes/plugins/daedalus/tools.py migrate-filesystem --workflow-root <path>` is a valid shell-runnable invocation.

- [ ] **Step 6: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_daedalus_migration.py -v`
Expected: PASS — all 7 tests green (6 from Task 1.1 + 1 new).

Run full suite to verify no regressions:
Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tools.py tests/test_daedalus_migration.py
git commit -m "$(cat <<'EOF'
feat(cli): daedalus migrate-filesystem subcommand

Operator-explicit invocation of the filesystem migrator.
init_daedalus_db also calls it transparently on startup; this CLI
is for manual operator runs (e.g. when investigating drift).
Adds a __main__ block to tools.py so operators can invoke
migrate-* subcommands from a shell during cutover.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5.6: Add `daedalus migrate-systemd` CLI subcommand

**Files:** `tools.py` (subcommand + handler), `tests/test_systemd_template_units.py`.

This task ALSO adds the systemd template unit content generator that Phase 6 builds on. Order: this task adds the new code; Phase 6 deprecates the old hardcoded service names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_systemd_template_units.py`:

```python
import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


TOOLS_PATH = Path(__file__).resolve().parents[1] / "tools.py"


def load_tools():
    spec = importlib.util.spec_from_file_location("daedalus_tools_for_systemd_test", TOOLS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_template_unit_active_mode():
    tools = load_tools()
    rendered = tools._render_template_unit(mode="active")
    assert "[Unit]" in rendered
    assert "Description=Daedalus active orchestrator" in rendered
    # Must contain %i placeholder for instance name
    assert "%i" in rendered
    assert "run-active" in rendered
    assert "/.hermes/plugins/daedalus/runtime.py" in rendered


def test_render_template_unit_shadow_mode():
    tools = load_tools()
    rendered = tools._render_template_unit(mode="shadow")
    assert "Description=Daedalus shadow orchestrator" in rendered
    assert "%i" in rendered
    assert "run-shadow" in rendered


def test_template_unit_filename():
    tools = load_tools()
    assert tools._template_unit_filename("active") == "daedalus-active@.service"
    assert tools._template_unit_filename("shadow") == "daedalus-shadow@.service"


def test_instance_unit_name():
    tools = load_tools()
    assert tools._instance_unit_name("active", "yoyopod") == "daedalus-active@yoyopod.service"
    assert tools._instance_unit_name("shadow", "blueprint") == "daedalus-shadow@blueprint.service"


def test_migrate_systemd_tolerant_of_missing_old_units(tmp_path, monkeypatch):
    """migrate-systemd should not fail when old units don't exist."""
    tools = load_tools()
    monkeypatch.setenv("DAEDALUS_SYSTEMD_USER_DIR", str(tmp_path))
    workflow_root = tmp_path / "wsroot"
    workflow_root.mkdir()

    # Stub systemctl so we don't actually invoke it
    captured_cmds = []
    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        # Pretend systemctl returns 0 for daemon-reload, error otherwise
        if "daemon-reload" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 5, "", "Unit not loaded")
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = tools.execute_raw_args(
        f"migrate-systemd --workflow-root {workflow_root}"
    )

    # Should succeed despite no old units, and install new template unit files
    assert "daedalus error" not in result.lower()
    assert (tmp_path / "daedalus-active@.service").exists()
    assert (tmp_path / "daedalus-shadow@.service").exists()


def test_migrate_systemd_removes_old_unit_files_when_present(tmp_path, monkeypatch):
    tools = load_tools()
    monkeypatch.setenv("DAEDALUS_SYSTEMD_USER_DIR", str(tmp_path))
    workflow_root = tmp_path / "wsroot"
    workflow_root.mkdir()

    # Seed old unit files
    (tmp_path / "yoyopod-relay-active.service").write_text("[Unit]\nDescription=old\n")
    (tmp_path / "yoyopod-relay-shadow.service").write_text("[Unit]\nDescription=old\n")

    captured_cmds = []
    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = tools.execute_raw_args(
        f"migrate-systemd --workflow-root {workflow_root}"
    )

    # Old unit files removed
    assert not (tmp_path / "yoyopod-relay-active.service").exists()
    assert not (tmp_path / "yoyopod-relay-shadow.service").exists()
    # New template units installed
    assert (tmp_path / "daedalus-active@.service").exists()
    assert (tmp_path / "daedalus-shadow@.service").exists()
    # systemctl daemon-reload was called
    assert any("daemon-reload" in cmd for cmd in captured_cmds)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_systemd_template_units.py -v`
Expected: FAIL — `_render_template_unit`, `_template_unit_filename`, `_instance_unit_name`, `migrate-systemd` don't exist.

- [ ] **Step 3: Add helpers in `tools.py`**

Add near the top of `tools.py` (after the existing service constants):

```python
DAEDALUS_TEMPLATE_UNIT_FILENAMES = {
    "active": "daedalus-active@.service",
    "shadow": "daedalus-shadow@.service",
}


def _template_unit_filename(mode: str) -> str:
    if mode not in DAEDALUS_TEMPLATE_UNIT_FILENAMES:
        raise DaedalusCommandError(f"unknown service mode: {mode}")
    return DAEDALUS_TEMPLATE_UNIT_FILENAMES[mode]


def _instance_unit_name(mode: str, workspace: str) -> str:
    template = _template_unit_filename(mode)
    # daedalus-active@.service -> daedalus-active@<workspace>.service
    return template.replace("@.service", f"@{workspace}.service")


def _render_template_unit(*, mode: str) -> str:
    if mode not in DAEDALUS_TEMPLATE_UNIT_FILENAMES:
        raise DaedalusCommandError(f"unknown service mode: {mode}")
    description = f"Daedalus {mode} orchestrator (workspace=%i)"
    runtime_command = f"run-{mode}"
    return "\n".join([
        "[Unit]",
        f"Description={description}",
        "After=default.target",
        "",
        "[Service]",
        "Type=simple",
        "WorkingDirectory=%h/.hermes/workflows/%i",
        "Environment=PYTHONUNBUFFERED=1",
        (
            f"ExecStart=/usr/bin/env python3 %h/.hermes/plugins/daedalus/runtime.py "
            f"{runtime_command} --workflow-root %h/.hermes/workflows/%i "
            f"--project-key %i --instance-id daedalus-{mode}-%i "
            f"--interval-seconds 30 --json"
        ),
        "Restart=always",
        "RestartSec=5",
        "",
        "[Install]",
        "WantedBy=default.target",
        "",
    ])
```

- [ ] **Step 4: Add `cmd_migrate_systemd` handler**

```python
def cmd_migrate_systemd(args, parser) -> str:
    workflow_root = args.workflow_root.expanduser().resolve()
    workspace = workflow_root.name  # last path segment, e.g. "yoyopod"
    systemd_dir = _systemd_user_dir()
    systemd_dir.mkdir(parents=True, exist_ok=True)

    actions: list[str] = []

    # 1. Stop + disable old units (tolerant of missing units)
    for old_name in ("yoyopod-relay-active.service", "yoyopod-relay-shadow.service"):
        old_path = systemd_dir / old_name
        if old_path.exists():
            # Try to stop (ignore failures: unit may not be loaded)
            subprocess.run(
                ["systemctl", "--user", "stop", old_name],
                check=False, capture_output=True,
            )
            subprocess.run(
                ["systemctl", "--user", "disable", old_name],
                check=False, capture_output=True,
            )
            old_path.unlink()
            actions.append(f"removed old unit {old_name}")

    # 2. Install new template units (overwrite if exists)
    for mode in ("active", "shadow"):
        template_filename = _template_unit_filename(mode)
        template_path = systemd_dir / template_filename
        template_path.write_text(_render_template_unit(mode=mode), encoding="utf-8")
        actions.append(f"installed template unit {template_filename}")

    # 3. systemctl daemon-reload
    subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        check=False, capture_output=True,
    )
    actions.append("daemon-reload")

    # Return summary
    lines = [f"migrate-systemd complete (workspace={workspace}):"]
    lines.extend(f"  - {a}" for a in actions)
    lines.append(f"to start active mode: systemctl --user start {_instance_unit_name('active', workspace)}")
    return "\n".join(lines)
```

- [ ] **Step 5: Wire the subcommand**

In `tools.py::configure_subcommands`, add:

```python
migrate_systemd_cmd = sub.add_parser(
    "migrate-systemd",
    help="Migrate relay-era systemd units to daedalus template units.",
)
migrate_systemd_cmd.add_argument(
    "--workflow-root",
    type=Path,
    default=DEFAULT_WORKFLOW_ROOT,
)
migrate_systemd_cmd.set_defaults(handler=cmd_migrate_systemd)
```

If using `if/elif` dispatch in `execute_raw_args`, add:

```python
if args.daedalus_command == "migrate-systemd":
    return cmd_migrate_systemd(args, parser)
```

Add `import subprocess` at the top of `tools.py` if not present.

- [ ] **Step 6: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_systemd_template_units.py -v`
Expected: PASS — all 6 tests green.

Run full suite: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tools.py tests/test_systemd_template_units.py
git commit -m "$(cat <<'EOF'
feat(cli): daedalus migrate-systemd + template unit helpers

New CLI subcommand removes old yoyopod-relay-{shadow,active}.service
unit files (tolerant of missing) and installs daedalus template units
(daedalus-{active,shadow}@.service). Operator runs this once during
the cutover.

Adds _render_template_unit, _template_unit_filename, _instance_unit_name
helpers used by Phase 6 to refactor the rest of the service profile
machinery.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 6 — Systemd template unit refactor

## Task 6.1: Refactor `SERVICE_PROFILES` to use template units

The existing `SERVICE_PROFILES` dict has hardcoded `service_name` strings (e.g., `"yoyopod-relay-active.service"`). Refactor to use the template unit filename and a callable that builds instance-qualified names.

**Files:** `tools.py` (constants + `SERVICE_PROFILES` + supporting helpers).

- [ ] **Step 1: Refactor constants and `SERVICE_PROFILES`**

In `tools.py`, replace the existing service-name constants and `SERVICE_PROFILES` block (around lines 31-50) with:

```python
DAEDALUS_INSTANCE_ID_FORMAT = "daedalus-{mode}-{workspace}"

SERVICE_PROFILES = {
    "shadow": {
        "template_unit": "daedalus-shadow@.service",
        "description": "Daedalus shadow orchestrator",
        "runtime_command": "run-shadow",
    },
    "active": {
        "template_unit": "daedalus-active@.service",
        "description": "Daedalus active orchestrator",
        "runtime_command": "run-active",
    },
}


def _instance_id_for(*, service_mode: str, workspace: str) -> str:
    return DAEDALUS_INSTANCE_ID_FORMAT.format(mode=service_mode, workspace=workspace)
```

Remove the now-unused constants:

```python
# DELETE:
DEFAULT_SHADOW_SERVICE_INSTANCE_ID = "relay-shadow-service-1"
DEFAULT_SHADOW_SERVICE_NAME = "yoyopod-relay-shadow.service"
DEFAULT_ACTIVE_SERVICE_INSTANCE_ID = "relay-active-service-1"
DEFAULT_ACTIVE_SERVICE_NAME = "yoyopod-relay-active.service"
DEFAULT_SERVICE_INSTANCE_ID = DEFAULT_SHADOW_SERVICE_INSTANCE_ID
DEFAULT_SERVICE_NAME = DEFAULT_SHADOW_SERVICE_NAME
```

- [ ] **Step 2: Update `_resolve_service_name` to take workspace**

The existing helper:

```python
def _resolve_service_name(*, service_name: str | None = None, service_mode: str = "shadow") -> str:
    return service_name or _service_profile(service_mode)["service_name"]
```

Becomes:

```python
def _resolve_service_name(
    *, service_name: str | None = None, service_mode: str = "shadow", workspace: str
) -> str:
    return service_name or _instance_unit_name(service_mode, workspace)
```

- [ ] **Step 3: Update `_resolve_service_instance_id`**

The existing helper:

```python
def _resolve_service_instance_id(*, instance_id: str | None = None, service_mode: str = "shadow") -> str:
    return instance_id or _service_profile(service_mode)["instance_id"]
```

Becomes:

```python
def _resolve_service_instance_id(
    *, instance_id: str | None = None, service_mode: str = "shadow", workspace: str
) -> str:
    return instance_id or _instance_id_for(service_mode=service_mode, workspace=workspace)
```

- [ ] **Step 4: Update `_render_service_unit`**

The existing function around line 184 still uses old paths. Replace its body to use the new template:

```python
def _render_service_unit(
    *,
    workflow_root: Path,
    project_key: str,
    instance_id: str,
    interval_seconds: int,
    service_mode: str = "shadow",
) -> str:
    # Now just delegates to _render_template_unit; kept for callers that
    # want a per-call rendering. Note: template units use %i so the
    # rendered output has a placeholder that systemd substitutes at
    # service activation time.
    return _render_template_unit(mode=service_mode)
```

- [ ] **Step 5: Update `install_supervised_service` and other callers**

Search for callers of `_resolve_service_name` and `_resolve_service_instance_id`:

```bash
grep -n "_resolve_service_name\|_resolve_service_instance_id" tools.py
```

Each call site needs to pass `workspace` (derived from `workflow_root.name`). Example:

```python
# Old
service_name = _resolve_service_name(service_mode=service_mode)
# New
workspace = workflow_root.name
service_name = _resolve_service_name(service_mode=service_mode, workspace=workspace)
```

For `install_supervised_service` and the related `service-*` commands: the function writes the unit file to `_systemd_user_dir() / template_filename`, not the instance-qualified name. The `start`/`stop`/`status` commands operate on the instance-qualified name.

**Specifically:**
- `service-install` writes the **template** file (e.g., `daedalus-active@.service`)
- `service-start`/`service-stop`/`service-status` operate on the **instance** (e.g., `daedalus-active@yoyopod.service`)
- The `_service_unit_path` for installation should return the template path; for status, return the instance path

The implementer should refactor `_service_unit_path` to take a flag distinguishing template vs instance, OR introduce a separate `_template_unit_path` helper. Either pattern is fine.

- [ ] **Step 6: Update tests**

```bash
grep -rn "yoyopod-relay-shadow\|yoyopod-relay-active\|relay-shadow-service-1\|relay-active-service-1\|DEFAULT_SHADOW_SERVICE\|DEFAULT_ACTIVE_SERVICE" tests/
```

For each test file with matches, update assertions to use the new template/instance names. Tests now expect:
- `daedalus-active@.service` (template) installed
- `daedalus-active@yoyopod.service` (instance) operated on for start/stop/status

- [ ] **Step 7: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -10`
Expected: PASS. If specific systemd-related tests fail, the implementer fixes them based on the new semantics.

- [ ] **Step 8: Commit**

```bash
git add tools.py tests/
git commit -m "$(cat <<'EOF'
refactor(systemd): SERVICE_PROFILES use template units

Replaces hardcoded yoyopod-relay-{shadow,active}.service strings with
template unit names + instance derivation by workspace key. The
template (daedalus-active@.service) ships once; instances
(daedalus-active@yoyopod.service) are activated at service-start time.

_resolve_service_name and _resolve_service_instance_id now take a
workspace parameter. Callers updated to derive workspace from
workflow_root.name.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6.2: Update `_evaluate_service_supervision` for template units

The doctor's service supervision check compares the live runtime's `current_mode` + `active_orchestrator_instance_id` against the expected service profile. Update to use the new instance ID format.

**Files:** `tools.py` (`_evaluate_service_supervision` function).

- [ ] **Step 1: Find the function**

```bash
grep -n "_evaluate_service_supervision\|active_orchestrator_instance_id" tools.py
```

Inspect the function body. It probably builds an expected `instance_id` from the old profile and compares against the DB row.

- [ ] **Step 2: Update expected instance ID derivation**

In the function, replace:

```python
expected_instance = profile["instance_id"]
# or similar logic using DEFAULT_*_SERVICE_INSTANCE_ID
```

with:

```python
workspace = workflow_root.name
expected_instance = _instance_id_for(service_mode=service_mode, workspace=workspace)
```

- [ ] **Step 3: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tools.py
git commit -m "$(cat <<'EOF'
refactor(doctor): _evaluate_service_supervision uses workspace-derived instance ID

Doctor now expects instance IDs of the form daedalus-{mode}-{workspace}
matching the new template unit instance shape.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6.3: Update plugin path strings in unit rendering

`_render_service_unit` and `_expected_plugin_runtime_path` reference the old `.hermes/plugins/hermes-relay/` install path. Update to `daedalus`.

**Files:** `tools.py`.

- [ ] **Step 1: Find references**

```bash
grep -n "hermes-relay" tools.py
```

Expected: 2-3 references in `_expected_plugin_runtime_path` and one in the unit rendering string (now removed by the template approach but the constant may still appear).

- [ ] **Step 2: Replace references**

Use Edit to change:
- `".hermes/plugins/hermes-relay/runtime.py"` → `".hermes/plugins/daedalus/runtime.py"`
- `".hermes/plugins/hermes-relay"` → `".hermes/plugins/daedalus"`

- [ ] **Step 3: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: some tests in `tests/test_install.py` and `tests/test_workflows_code_review_paths.py` likely fail because they assert the old plugin path. Update those tests in the same commit.

- [ ] **Step 4: Update test assertions**

```bash
grep -rn "hermes-relay" tests/test_install.py tests/test_workflows_code_review_paths.py
```

For each match, replace with `daedalus`.

In `tests/test_install.py`, the symlink test (lines 46-73) uses `~/.hermes/plugins/hermes-relay` as the symlink target — update to `~/.hermes/plugins/daedalus`.

- [ ] **Step 5: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools.py tests/
git commit -m "$(cat <<'EOF'
refactor(paths): plugin install path .hermes/plugins/hermes-relay -> daedalus

tools.py + paths.py + workspace.py + tests now reference the
daedalus-named plugin install directory. scripts/install.py
PLUGIN_NAME constant updated in Phase 7.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6.4: Update `paths.py` and `workspace.py` plugin path references

`paths.py::plugin_entrypoint_path` and `workspace.py` both build paths under `.hermes/plugins/hermes-relay/`. Update.

**Files:**
- `workflows/code_review/paths.py`
- `workflows/code_review/workspace.py`

- [ ] **Step 1: Find references**

```bash
grep -n "hermes-relay" workflows/code_review/paths.py workflows/code_review/workspace.py
```

Expected: ~4 references.

- [ ] **Step 2: Replace in `paths.py`**

In `workflows/code_review/paths.py`, find:

```python
def plugin_entrypoint_path(workflow_root: Path) -> Path:
    """...
    Lives at ``<workflow_root>/.hermes/plugins/hermes-relay/workflows/__main__.py``.
    ...
    """
    root = workflow_root.resolve()
    return (
        root / ".hermes" / "plugins" / "hermes-relay" / "workflows" / "__main__.py"
    )
```

Replace `hermes-relay` with `daedalus` in the path and the docstring.

- [ ] **Step 3: Replace in `workspace.py`**

In `workflows/code_review/workspace.py`, find (around line 244):

```python
plugin_root = workspace_root / ".hermes" / "plugins" / "hermes-relay"
```

Replace with:

```python
plugin_root = workspace_root / ".hermes" / "plugins" / "daedalus"
```

- [ ] **Step 4: Update tests if any references remain**

```bash
grep -rn "hermes-relay" tests/
```

For each match in test files, update to `daedalus`.

- [ ] **Step 5: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add workflows/code_review/paths.py workflows/code_review/workspace.py tests/
git commit -m "$(cat <<'EOF'
refactor(paths): paths.py + workspace.py reference .hermes/plugins/daedalus

plugin_entrypoint_path and the workspace adapter loader now look up
modules under the daedalus install directory.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 7 — Plugin / asset / skill renames

## Task 7.1: Update `scripts/install.py` `PLUGIN_NAME`

**Files:** `scripts/install.py`, `tests/test_install.py`.

- [ ] **Step 1: Update `PLUGIN_NAME`**

In `scripts/install.py`, find:

```python
PLUGIN_NAME = "hermes-relay"
```

Replace with:

```python
PLUGIN_NAME = "daedalus"
```

Also update the docstrings/comments mentioning `hermes-relay`:

```bash
grep -n "hermes-relay" scripts/install.py
```

For each match, replace.

- [ ] **Step 2: Update the runtime deps error message**

Find:

```python
"hermes-relay plugin requires the following python modules on the host: "
```

Replace with:

```python
"daedalus plugin requires the following python modules on the host: "
```

- [ ] **Step 3: Update `tests/test_install.py`**

```bash
grep -n "hermes-relay" tests/test_install.py
```

For each match, replace `hermes-relay` with `daedalus`. The symlink test fixtures (lines 46-73) need their target paths updated.

- [ ] **Step 4: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/test_install.py -v`
Expected: PASS — all 4 tests green.

Run full suite: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/install.py tests/test_install.py
git commit -m "$(cat <<'EOF'
refactor(install): PLUGIN_NAME hermes-relay -> daedalus

Plugin installs to ~/.hermes/plugins/daedalus. Symlink-target
test updated to expect the new path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7.2: Rename asset files and update embedded SVG text

**Files:** `assets/hermes-relay-icon.svg`, `assets/hermes-relay-wordmark.svg`.

- [ ] **Step 1: Inspect SVG content for "Hermes Relay" text**

```bash
grep "Hermes Relay\|hermes-relay\|HERMES RELAY" assets/*.svg
```

Note any text nodes that need to be rewritten to "Daedalus".

- [ ] **Step 2: Rename files**

```bash
git mv assets/hermes-relay-icon.svg assets/daedalus-icon.svg
git mv assets/hermes-relay-wordmark.svg assets/daedalus-wordmark.svg
```

- [ ] **Step 3: Update embedded text in the wordmark SVG**

Open `assets/daedalus-wordmark.svg`. Find any `<text>` tags or `tspan`s containing "Hermes Relay" / "HERMES RELAY" / "hermes-relay" and replace with "Daedalus" / "DAEDALUS" / "daedalus" respectively. Visual elements (shapes, colors, gradients, paths) untouched.

If the icon SVG contains text (unlikely for an icon), do the same.

- [ ] **Step 4: Find and update references to old asset filenames**

```bash
grep -rn "hermes-relay-icon\|hermes-relay-wordmark" --include="*.md" --include="*.html"
```

For each match (likely in `README.md` and possibly some skill docs), replace with the new filename.

- [ ] **Step 5: Commit**

```bash
git add assets/ README.md
git commit -m "$(cat <<'EOF'
refactor(assets): rename SVG icon + wordmark to daedalus-*.svg

Filename rename + embedded SVG text "Hermes Relay" -> "Daedalus".
Visual identity (shapes, colors) untouched. README references
updated to the new filenames.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7.3: Rename `skills/hermes-relay-*` directories

**Files:** Skill directories under `skills/`.

- [ ] **Step 1: Use `git mv` for each directory rename**

```bash
cd /home/radxa/WS/hermes-relay
git mv skills/hermes-relay-architecture skills/daedalus-architecture
git mv skills/hermes-relay-hardening-slices skills/daedalus-hardening-slices
git mv skills/hermes-relay-model1-project-layout skills/daedalus-model1-project-layout
git mv skills/hermes-relay-retire-watchdog-and-migrate-control-schema skills/daedalus-retire-watchdog-and-migrate-control-schema
```

- [ ] **Step 2: Find docs that link to the old skill directory names**

```bash
grep -rn "hermes-relay-architecture\|hermes-relay-hardening-slices\|hermes-relay-model1-project-layout\|hermes-relay-retire-watchdog" --include="*.md"
```

For each match, replace with the new directory name. Common locations: cross-references in other skills, README, operator cheat sheet.

- [ ] **Step 3: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: `tests/test_plugin_skills.py` may fail if it asserts the old skill names. Continue to next step before running.

- [ ] **Step 4: Update `tests/test_plugin_skills.py`**

In `tests/test_plugin_skills.py:31-35`, the expected skill set includes:

```python
"hermes-relay-architecture",
"hermes-relay-model1-project-layout",
...
"hermes-relay-hardening-slices",
"hermes-relay-retire-watchdog-and-migrate-control-schema",
```

Replace each with the `daedalus-*` equivalent.

- [ ] **Step 5: Run test suite again**

Run: `/usr/bin/python3 -m pytest tests/test_plugin_skills.py -v`
Expected: PASS.

Run full suite: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor(skills): rename skills/hermes-relay-* to skills/daedalus-*

4 skill directories renamed (architecture, hardening-slices,
model1-project-layout, retire-watchdog-and-migrate-control-schema).
Cross-references in docs updated. test_plugin_skills.py expected
set updated.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7.4: Rename `skills/yoyopod-relay-*` directories

**Files:** Skill directories under `skills/`.

- [ ] **Step 1: Rename via `git mv`**

```bash
cd /home/radxa/WS/hermes-relay
git mv skills/yoyopod-relay-alerts-monitoring skills/yoyopod-daedalus-alerts-monitoring
git mv skills/yoyopod-relay-outage-alerts skills/yoyopod-daedalus-outage-alerts
```

- [ ] **Step 2: Find references in docs**

```bash
grep -rn "yoyopod-relay-alerts-monitoring\|yoyopod-relay-outage-alerts" --include="*.md"
```

Replace each with the new directory name.

- [ ] **Step 3: Update `tests/test_plugin_skills.py`**

The test's expected skill set may reference these names. Update to `yoyopod-daedalus-alerts-monitoring` and `yoyopod-daedalus-outage-alerts`.

- [ ] **Step 4: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor(skills): rename yoyopod-relay-* to yoyopod-daedalus-*

skills/yoyopod-relay-alerts-monitoring -> skills/yoyopod-daedalus-alerts-monitoring
skills/yoyopod-relay-outage-alerts -> skills/yoyopod-daedalus-outage-alerts

Project-prefixed skills (still scoped to yoyopod) get the daedalus
infix to match the engine identity.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 8 — Documentation prose + version bump + ADR

## Task 8.1: `plugin.yaml` rename + version bump

**Files:** `/home/radxa/WS/hermes-relay/plugin.yaml`.

- [ ] **Step 1: Update `plugin.yaml`**

Open `plugin.yaml`. Replace contents with:

```yaml
name: daedalus
version: 0.3.0
description: Daedalus workflow engine and operator control surface.
author: Hermes Agent
provides_hooks: []
provides_tools: []
```

- [ ] **Step 2: Run test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS (test_install.py asserts plugin.yaml exists; doesn't parse contents).

- [ ] **Step 3: Commit**

```bash
git add plugin.yaml
git commit -m "$(cat <<'EOF'
chore(plugin): bump to 0.3.0 + rename hermes-relay -> daedalus

Identity bump (rebranding). Description updated to reflect that
Daedalus is the workflow engine + operator control surface, not
a single-purpose relay.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8.2: Mechanical find-replace across `*.md` docs

**Files:** All `*.md` files under `README.md`, `docs/`, `skills/*/SKILL.md`.

This is a high-volume mechanical change. The implementer should be careful to preserve historical artifacts (ADRs and prior specs/plans).

- [ ] **Step 1: Inventory the scope**

```bash
find /home/radxa/WS/hermes-relay -name "*.md" -not -path "*/.git/*" -not -path "*/.claude/*" | xargs grep -l "Hermes Relay\|hermes-relay\|HERMES_RELAY\|/relay\|relay\.db\|relay-events" 2>/dev/null | sort
```

Expected: ~10-15 files.

- [ ] **Step 2: Identify allowlisted files (do NOT modify)**

These contain old identifiers as historical artifacts and stay untouched:
- `docs/adr/ADR-0001-yoyopod-core-model1-adapter-boundary.md`
- `docs/adr/ADR-0002-workflows-contract.md`
- `docs/superpowers/specs/2026-04-24-workflows-contract-and-code-review-design.md`
- `docs/superpowers/plans/2026-04-24-workflows-contract-and-code-review.md`
- `docs/superpowers/specs/2026-04-25-daedalus-rename-design.md` (the spec for THIS rename — references old names by necessity)
- `docs/superpowers/plans/2026-04-25-daedalus-rename.md` (this plan — same)

- [ ] **Step 3: Mechanical replace per non-allowlisted file**

For each file in the inventory minus allowlisted ones, perform the following replacements via Edit (with `replace_all: true`):

| `old_string` | `new_string` |
|---|---|
| `hermes-relay` | `daedalus` |
| `Hermes Relay` | `Daedalus` |
| `HERMES_RELAY_` | `DAEDALUS_` |
| `relay.db` | `daedalus.db` |
| `relay-events.jsonl` | `daedalus-events.jsonl` |
| `hermes-relay-alert-state` | `daedalus-alert-state` |
| `state/relay/` | `state/daedalus/` |
| `/relay status` | `/daedalus status` |
| `/relay shadow-report` | `/daedalus shadow-report` |
| `/relay doctor` | `/daedalus doctor` |
| `/relay active-gate-status` | `/daedalus active-gate-status` |
| `/relay set-active-execution` | `/daedalus set-active-execution` |
| `/relay service-` | `/daedalus service-` |
| `/relay cutover-switch` | `/daedalus cutover-switch` |
| `yoyopod-relay-active.service` | `daedalus-active@yoyopod.service` |
| `yoyopod-relay-shadow.service` | `daedalus-shadow@yoyopod.service` |
| `RelayCommandError` | `DaedalusCommandError` |

For phrases that don't fit a fixed find-replace (like "the relay" vs "the runtime"/"the engine"/"Daedalus" depending on context), do a manual pass after the mechanical replacements.

**Recommended workflow:** for each file:
1. Open via Read
2. Apply each Edit with `replace_all: true` for matching `old_string`
3. After all mechanical edits, re-Read and scan for remaining "relay" / "Relay" prose; manually replace contextually

- [ ] **Step 4: Run tests**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/ skills/
git commit -m "$(cat <<'EOF'
docs: mechanical find-replace hermes-relay -> daedalus

README, docs/architecture.md, docs/operator-cheat-sheet.md, all
skill SKILL.md files, ADRs (except historical), specs (except
2026-04-25-daedalus-rename-design and immediate predecessor).

Allowlisted historical artifacts (ADR-0001/0002, prior workflows-
contract spec/plan) untouched — they record what was true at the
time.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8.3: Write ADR-0003

**Files:** `/home/radxa/WS/hermes-relay/docs/adr/ADR-0003-daedalus-rebrand.md` (NEW).

- [ ] **Step 1: Create ADR-0003**

Write to `docs/adr/ADR-0003-daedalus-rebrand.md`:

```markdown
# ADR-0003: Daedalus rebrand

**Status:** Accepted (2026-04-25)
**Supersedes:** Project identity from ADR-0001 / ADR-0002 era ("hermes-relay")

## Context

The plugin originally shipped as `hermes-relay` — a name that described
its initial role (a relay/orchestrator inside the Hermes plugin
ecosystem). The project has since evolved into a generic workflow
engine that orchestrates other agents through structured workflows
(code-review first, with Testing, Security-Review, etc. on the
roadmap). The "relay" framing no longer captures what the project does.

The workflows-contract migration (ADR-0002) decoupled "workflow type"
from "workspace instance" but kept the engine's identity tied to its
historical name. This created confusion: operators saw `relay` in some
surfaces and `workflow` in others, with no clear semantic boundary.

## Decision

Rebrand the engine to **Daedalus**. The master craftsman of Greek
myth — patron of artisans, builder of complex devices. The name
preserves the Hermes mythological lineage while precisely describing
what the project is: an engine that orchestrates other agents through
structured workflows.

The rename is a single-sweep, no-backward-compat migration:

- Repo: `hermes-relay` → `daedalus`
- Plugin: `plugin.yaml` `name: hermes-relay` → `daedalus`; install dir
  `~/.hermes/plugins/hermes-relay` → `~/.hermes/plugins/daedalus`
- Slash commands: `/relay <cmd>` → `/daedalus <cmd>` (engine commands).
  New `/workflow <name> <cmd>` slash command for per-workflow CLI access.
- Filesystem: `state/relay/relay.db` → `state/daedalus/daedalus.db` (with
  WAL/SHM sidecars), `memory/relay-events.jsonl` →
  `memory/daedalus-events.jsonl`, `memory/hermes-relay-alert-state.json`
  → `memory/daedalus-alert-state.json`
- Env vars: `HERMES_RELAY_WORKFLOW_ROOT` / `YOYOPOD_RELAY_WORKFLOW_ROOT`
  → `DAEDALUS_WORKFLOW_ROOT`
- Systemd: hardcoded `yoyopod-relay-{shadow,active}.service` → template
  units `daedalus-{shadow,active}@<workspace>.service` (enables multiple
  workspaces on one host)
- Internal Python identifiers: `RelayCommandError` →
  `DaedalusCommandError`, `init_relay_db` → `init_daedalus_db`,
  `append_relay_event` → `append_daedalus_event`,
  `RELAY_SCHEMA_VERSION` → `DAEDALUS_SCHEMA_VERSION`, etc.
- SQL schema: `relay_runtime` table → `daedalus_runtime`, `runtime_id`
  row identity `'relay'` → `'daedalus'`, event types
  `relay_runtime_*` → `daedalus_runtime_*`

A one-shot filesystem migrator (`migration.py`) runs at runtime
startup, transparently renaming relay-era files (including SQLite
WAL/SHM sidecars). A separate `daedalus migrate-systemd` operator
command handles the systemd cutover.

## Consequences

Positive:

- Engine identity matches what the engine does
- Slash command split (`/daedalus` engine vs `/workflow` per-workflow)
  cleanly separates what's being controlled
- Systemd template units enable multiple workspaces on one host
- Hard cut (no backward compat) avoids the dual-name period that would
  confuse operators

Negative:

- Operators need to learn the new identity (cheat sheet + skill docs
  capture the new vocabulary)
- Live cutover requires ~30s downtime (acceptable since the workspace
  is idle when the cutover runs)
- External cron jobs / scripts referencing old paths need update (the
  migrator handles file renames; environment / unit references must be
  manually updated)

## Out of scope

- Visual identity redesign (current SVGs keep their visuals; only
  filename + embedded text strings change)
- Brand voice / marketing copy beyond mechanical find-replace
- Multi-workspace operation beyond what the systemd template enables
- New workflow types (Testing, Security-Review, ...) — separate effort

## References

- Spec: `docs/superpowers/specs/2026-04-25-daedalus-rename-design.md`
- Plan: `docs/superpowers/plans/2026-04-25-daedalus-rename.md`
- Predecessor: `docs/adr/ADR-0002-workflows-contract.md`
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/ADR-0003-daedalus-rebrand.md
git commit -m "$(cat <<'EOF'
docs(adr): ADR-0003 captures the daedalus rebrand decision

Records the single-sweep rename from hermes-relay to Daedalus,
the slash command split (/daedalus engine vs /workflow per-workflow),
the systemd template unit redesign, and the no-backward-compat
posture.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 9 — Final verification

## Task 9.1: Grep audit for residual relay-era strings

The whole point of the rename is that the codebase consistently uses the new identity. This task verifies that with a grep audit and surfaces anything missed.

**Files:** No file modifications expected; this task is pure audit. Any findings get fixed inline.

- [ ] **Step 1: Run the audit**

Use this script as a single bash command (or run individual greps):

```bash
cd /home/radxa/WS/hermes-relay

ALLOWLIST_REGEX='/(\.git|\.claude/worktrees|docs/adr/ADR-000[12]|docs/superpowers/(specs|plans)/2026-04-2[45])/'

for pattern in \
    "hermes-relay" \
    "Hermes Relay" \
    "HERMES_RELAY" \
    "_load_relay_module" \
    "RelayCommandError" \
    "RelayArgumentParser" \
    "init_relay_db" \
    "append_relay_event" \
    "RELAY_SCHEMA_VERSION" \
    "relay\\.db" \
    "relay-events\\.jsonl" \
    "yoyopod-relay-active\\.service" \
    "yoyopod-relay-shadow\\.service" \
    "yoyopod_relay_plugin" \
    "args\\.relay_command" \
    "DEFAULT_SHADOW_SERVICE_NAME" \
    "DEFAULT_ACTIVE_SERVICE_NAME"; do
    echo "=== $pattern ==="
    grep -rn "$pattern" --include="*.py" --include="*.yaml" --include="*.md" --include="*.sh" --include="*.svg" 2>/dev/null \
        | grep -vE "$ALLOWLIST_REGEX" \
        || echo "  (no matches outside allowlist)"
done
```

- [ ] **Step 2: Triage findings**

For each unexpected match:
- If it's a missed rename, fix it inline (Edit + commit + re-run grep audit)
- If it's a legitimate historical reference (e.g. inside a quoted error message that's part of the plan text), confirm it should stay

- [ ] **Step 3: Run full test suite**

Run: `/usr/bin/python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5`
Expected: PASS — final number of tests passing should be 244 (originals, all renamed in place) + 6 (test_daedalus_migration) + 3 (test_daedalus_db_schema_migration) + 6 (test_systemd_template_units) + 3 (test_workflow_slash_command) + 1 (test_cli_migrate_filesystem) = **263 passing**.

Run unrelated-failure tests: `/usr/bin/python3 -m pytest tests/test_runtime_tools_alerts.py -q 2>&1 | tail -10`
Expected: pre-existing failure persists; no NEW failures.

- [ ] **Step 4: If any fixes were committed, also bump plugin.yaml back-revision is unnecessary**

Plan ends here. If grep audit was clean (no fixes needed), no commit. If fixes were committed in step 2, those land as-is.

---

## Task 9.2: Smoke test plan (manual, post-merge)

The cutover sequence in the spec (Section 6) is the live operational ritual. **Not part of plan execution** but document it here for the operator.

**Pre-flight (on YoyoPod machine):**

1. Confirm idle: `python3 -m workflows --workflow-root ~/.hermes/workflows/yoyopod status` → no active lane
2. Note current systemd state: `systemctl --user is-active yoyopod-relay-active.service`

**Cutover sequence:**

1. `systemctl --user stop yoyopod-relay-active.service`
2. `cd ~/WS/hermes-relay && git pull`
3. `./scripts/install.sh` (installs new payload to `~/.hermes/plugins/daedalus/`)
4. `/usr/bin/python3 ~/.hermes/plugins/daedalus/tools.py migrate-systemd --workflow-root ~/.hermes/workflows/yoyopod`
5. `systemctl --user start daedalus-active@yoyopod.service`
   (first run of `runtime.py` triggers the filesystem migrator automatically — DB + WAL/SHM sidecars + event log + alert state files renamed)
6. Verify: `/daedalus status` → healthy, `/daedalus doctor` → no issues
7. Optional smoke: `/workflow code-review status` → idle, no active lane

**Total downtime:** ~30 seconds.

**Rollback:** `git revert` the rename commits; reinstall the old payload via `./scripts/install.sh`; manually rename `daedalus.db` back to `relay.db` (and the WAL/SHM sidecars + event log + alert state files); manually reinstall the old systemd units (or restore from backup). Documented in operator skill.

---

# Plan summary

**Total tasks: 31** across 9 phases.

| Phase | Focus | Tasks |
|---|---|---|
| 1 | Migration foundation (additive) | 1.1, 1.2, 1.3 (3) |
| 2 | Path constants + env vars | 2.1, 2.2 (2) |
| 3 | Python identifier renames | 3.1–3.7 (7) |
| 4 | SQL schema + event log identifiers | 4.1, 4.2, 4.3 (3) |
| 5 | CLI surface (slash commands, migrate-* subcommands) | 5.1–5.6 (6) |
| 6 | Systemd template unit refactor | 6.1, 6.2, 6.3, 6.4 (4) |
| 7 | Plugin/asset/skill renames | 7.1, 7.2, 7.3, 7.4 (4) |
| 8 | Docs + version bump + ADR | 8.1, 8.2, 8.3 (3) |
| 9 | Final verification + cutover doc | 9.1, 9.2 (2) — 9.2 is doc-only |

**Test count math:**

| | Tests |
|---|---|
| Baseline | 244 passing + 1 pre-existing failure |
| + Task 1.1 (`test_daedalus_migration.py`, 6 tests) | 250 |
| + Task 1.2 (`test_daedalus_db_schema_migration.py`, 3 tests) | 253 |
| + Task 5.4 (`test_workflow_slash_command.py`, 3 tests) | 256 |
| + Task 5.5 (1 new test in `test_daedalus_migration.py`) | 257 |
| + Task 5.6 (`test_systemd_template_units.py`, 6 tests) | 263 |

**Expected final state: 263 passing + 1 pre-existing failure unchanged.**

**Cutover (Task 9.2) is a manual operator step** — not part of plan execution. It runs separately on the live YoyoPod machine after the plan has merged to `main`.
