"""Phase D-2 tests: function renames + alias drops."""
from __future__ import annotations

import pytest


def test_fetch_external_review_aliased():
    from workflows.code_review.reviews import fetch_external_review, fetch_codex_cloud_review
    assert fetch_codex_cloud_review is fetch_external_review


def test_summarize_external_review_aliased():
    from workflows.code_review.reviews import summarize_external_review, summarize_codex_cloud_review
    assert summarize_codex_cloud_review is summarize_external_review


def test_build_external_review_thread_aliased():
    from workflows.code_review.reviews import build_external_review_thread, build_codex_cloud_thread
    assert build_codex_cloud_thread is build_external_review_thread


def test_should_dispatch_external_review_repair_handoff_aliased():
    from workflows.code_review.reviews import (
        should_dispatch_external_review_repair_handoff,
        should_dispatch_codex_cloud_repair_handoff,
    )
    assert should_dispatch_codex_cloud_repair_handoff is should_dispatch_external_review_repair_handoff


def test_external_review_placeholder_aliased():
    from workflows.code_review.reviews import external_review_placeholder, codex_cloud_placeholder
    assert codex_cloud_placeholder is external_review_placeholder


def test_build_external_review_repair_handoff_payload_aliased():
    from workflows.code_review.reviews import (
        build_external_review_repair_handoff_payload,
        build_codex_cloud_repair_handoff_payload,
    )
    assert build_codex_cloud_repair_handoff_payload is build_external_review_repair_handoff_payload


def test_record_external_review_repair_handoff_aliased():
    from workflows.code_review.reviews import (
        record_external_review_repair_handoff,
        record_codex_cloud_repair_handoff,
    )
    assert record_codex_cloud_repair_handoff is record_external_review_repair_handoff


def test_fetch_external_review_pr_body_signal_aliased():
    from workflows.code_review.reviews import (
        fetch_external_review_pr_body_signal,
        fetch_codex_pr_body_signal,
    )
    assert fetch_codex_pr_body_signal is fetch_external_review_pr_body_signal
