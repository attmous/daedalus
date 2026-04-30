import json
import sqlite3


def test_engine_storage_writes_json_and_jsonl(tmp_path):
    from engine.storage import append_jsonl, load_optional_json, write_json_atomic, write_text_atomic

    payload_path = tmp_path / "state" / "payload.json"
    write_json_atomic(payload_path, {"b": 2, "a": 1})

    assert payload_path.read_text(encoding="utf-8") == '{\n  "a": 1,\n  "b": 2\n}\n'
    assert load_optional_json(payload_path) == {"a": 1, "b": 2}

    list_path = tmp_path / "state" / "list.json"
    list_path.write_text("[]", encoding="utf-8")
    assert load_optional_json(list_path) is None

    text_path = tmp_path / "state" / "note.txt"
    write_text_atomic(text_path, "hello")
    assert text_path.read_text(encoding="utf-8") == "hello"

    log_path = tmp_path / "audit" / "events.jsonl"
    append_jsonl(log_path, {"event": "b", "at": "now"})
    assert json.loads(log_path.read_text(encoding="utf-8")) == {"at": "now", "event": "b"}


def test_engine_scheduler_restores_legacy_shapes_and_snapshots():
    from engine.scheduler import build_scheduler_payload, restore_scheduler_state, retry_due_at

    restored = restore_scheduler_state(
        {
            "retryQueue": [
                {
                    "issueId": "42",
                    "identifier": "#42",
                    "attempt": 2,
                    "dueAtEpoch": 125.0,
                    "currentAttempt": 1,
                }
            ],
            "running": [
                {
                    "issueId": "43",
                    "workerId": "worker:43",
                    "startedAtEpoch": 100.0,
                    "heartbeatAtEpoch": 110.0,
                    "cancelRequested": True,
                }
            ],
            "codexTotals": {"total_tokens": 5},
            "codex_threads": {"42": {"thread_id": "thread-1", "turn_id": "turn-1"}},
        },
        now_epoch=200.0,
    )

    assert restored.retry_entries["42"]["due_at_epoch"] == 125.0
    assert restored.recovered_running[0]["issue_id"] == "43"
    assert restored.recovered_running[0]["cancel_requested"] is True
    assert restored.codex_totals == {"total_tokens": 5}
    assert restored.codex_threads["42"]["thread_id"] == "thread-1"
    assert retry_due_at(restored.retry_entries["42"], default=999.0) == 125.0

    payload = build_scheduler_payload(
        workflow="issue-runner",
        retry_entries=restored.retry_entries,
        running_entries={"43": restored.recovered_running[0]},
        codex_totals=restored.codex_totals,
        codex_threads=restored.codex_threads,
        now_iso="2026-04-30T00:00:00Z",
        now_epoch=200.0,
    )

    assert payload["workflow"] == "issue-runner"
    assert payload["retry_queue"][0]["due_in_ms"] == 0
    assert payload["running"][0]["running_for_ms"] == 100000
    assert payload["codex_threads"]["42"]["thread_id"] == "thread-1"


def test_engine_audit_writer_fans_out_best_effort(tmp_path):
    from engine.audit import make_audit_fn

    calls = []

    def publisher(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("subscriber failed")

    audit = make_audit_fn(
        audit_log_path=tmp_path / "audit.jsonl",
        now_iso=lambda: "2026-04-30T00:00:00Z",
        publisher=publisher,
    )

    audit("tick", "ran one tick", issue_id="42")

    row = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8"))
    assert row == {
        "action": "tick",
        "at": "2026-04-30T00:00:00Z",
        "issue_id": "42",
        "summary": "ran one tick",
    }
    assert calls == [{"action": "tick", "summary": "ran one tick", "extra": {"issue_id": "42"}}]


def test_engine_sqlite_connection_sets_runtime_pragmas(tmp_path):
    from engine.sqlite import connect_daedalus_db

    db_path = tmp_path / "runtime" / "state" / "daedalus.db"
    conn = connect_daedalus_db(db_path)
    try:
        assert db_path.exists()
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()

    reopened = sqlite3.connect(db_path)
    try:
        assert reopened.execute("SELECT 1").fetchone()[0] == 1
    finally:
        reopened.close()
