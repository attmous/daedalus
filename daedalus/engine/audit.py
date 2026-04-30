from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .storage import append_jsonl


AuditPublisher = Callable[..., Any]
Clock = Callable[[], str]


def make_audit_fn(
    *,
    audit_log_path: Path,
    now_iso: Clock,
    publisher: AuditPublisher | None = None,
) -> Callable[..., None]:
    """Build a JSONL audit writer with best-effort subscriber fanout."""

    def audit(action: str, summary: str, **extra: Any) -> None:
        append_jsonl(
            audit_log_path,
            {
                "at": now_iso(),
                "action": action,
                "summary": summary,
                **extra,
            },
        )
        if publisher is None:
            return
        try:
            publisher(action=action, summary=summary, extra=dict(extra))
        except Exception:
            # Observability subscribers must never break workflow execution.
            pass

    return audit
