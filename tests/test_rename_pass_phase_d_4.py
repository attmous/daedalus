"""Phase D-4 tests: drop D-2/D-3 aliases + per-thread source rename."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("name", [
    "fetch_codex_cloud_review",
    "summarize_codex_cloud_review",
    "build_codex_cloud_thread",
    "should_dispatch_codex_cloud_repair_handoff",
    "codex_cloud_placeholder",
    "build_codex_cloud_repair_handoff_payload",
    "record_codex_cloud_repair_handoff",
    "fetch_codex_pr_body_signal",
])
def test_codex_cloud_alias_dropped(name):
    """All 8 Phase D-2 module-level aliases should be gone."""
    from workflows.code_review import reviews
    assert not hasattr(reviews, name), f"{name} alias should have been removed"


def test_build_external_review_thread_uses_externalReview_source():
    """Per-thread source label is provider-neutral after D-4."""
    from workflows.code_review.reviews import build_external_review_thread

    out = build_external_review_thread(
        node={"id": "T1", "isResolved": False, "isOutdated": False, "path": "a.py", "line": 1},
        comment={"body": "x", "url": "https://x", "createdAt": "2026-01-01T00:00:00Z"},
        severity="minor", summary="x",
        pr_signal=None, signal_epoch=None, comment_epoch=None,
    )
    assert out["source"] == "externalReview"
