"""Shared Daedalus engine primitives.

Workflow packages own lifecycle policy. This package owns reusable runtime
mechanics: durable file IO, audit writes, scheduler snapshots, and SQLite setup.
"""

from .audit import make_audit_fn
from .driver import WorkflowDriver
from .scheduler import (
    RestoredSchedulerState,
    build_scheduler_payload,
    codex_threads_snapshot,
    restore_scheduler_state,
    retry_due_at,
    retry_queue_snapshot,
    running_snapshot,
)
from .sqlite import connect_daedalus_db
from .storage import append_jsonl, load_optional_json, write_json_atomic, write_text_atomic

__all__ = [
    "RestoredSchedulerState",
    "WorkflowDriver",
    "append_jsonl",
    "build_scheduler_payload",
    "codex_threads_snapshot",
    "connect_daedalus_db",
    "load_optional_json",
    "make_audit_fn",
    "restore_scheduler_state",
    "retry_due_at",
    "retry_queue_snapshot",
    "running_snapshot",
    "write_json_atomic",
    "write_text_atomic",
]
