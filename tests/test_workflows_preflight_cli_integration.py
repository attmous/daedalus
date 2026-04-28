"""Smoke integration: run_cli + preflight failure path.

Builds a minimal workflow_root with an unsupported runtime.kind and
verifies:

1. ``workflows.run_cli`` raises ``WorkflowContractError`` with the
   preflight error code/detail in the message.
2. A ``daedalus.dispatch_skipped`` event with ``code=unsupported_runtime_kind``
   was appended to the workflow event log.
"""
from __future__ import annotations

import importlib
import json
import sys

import pytest


def _reset_workflows_module_cache():
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]


def _write_workflow_with_preflight(tmp_path, *, name="preflight-wf"):
    """Drop a minimal workflow package whose run_preflight delegates to the
    real code_review.preflight.run_preflight (so we exercise the real enum)."""
    slug = name.replace("-", "_")
    (tmp_path / "workflows" / slug).mkdir(parents=True, exist_ok=True)
    schema = (
        "$schema: http://json-schema.org/draft-07/schema#\n"
        "type: object\n"
        "required: [workflow, schema-version]\n"
        "properties:\n"
        "  workflow: {type: string}\n"
        "  schema-version: {type: integer}\n"
        "  runtime:\n"
        "    type: object\n"
        "    properties:\n"
        "      kind: {type: string}\n"
    )
    (tmp_path / "workflows" / slug / "schema.yaml").write_text(schema, encoding="utf-8")
    (tmp_path / "workflows" / slug / "__init__.py").write_text(
        f"from pathlib import Path\n"
        f"from workflows.code_review.preflight import run_preflight\n"
        f"NAME = {name!r}\n"
        f"SUPPORTED_SCHEMA_VERSIONS = (1,)\n"
        f"CONFIG_SCHEMA_PATH = Path(__file__).parent / 'schema.yaml'\n"
        f"def make_workspace(*, workflow_root, config):\n"
        f"    return {{}}\n"
        f"def cli_main(ws, argv):\n"
        f"    return 0\n",
        encoding="utf-8",
    )


def test_run_cli_emits_dispatch_skipped_on_preflight_failure(tmp_path, monkeypatch):
    _write_workflow_with_preflight(tmp_path, name="preflight-wf")
    workflow_root = tmp_path / "workflow_root"
    (workflow_root / "config").mkdir(parents=True)
    (workflow_root / "config" / "workflow.yaml").write_text(
        "workflow: preflight-wf\n"
        "schema-version: 1\n"
        "runtime:\n"
        "  kind: totally-bogus\n",
        encoding="utf-8",
    )

    _reset_workflows_module_cache()
    workflows = importlib.import_module("workflows")
    monkeypatch.setattr(
        workflows, "__path__", list(workflows.__path__) + [str(tmp_path / "workflows")]
    )

    with pytest.raises(workflows.WorkflowContractError) as exc:
        workflows.run_cli(workflow_root, ["tick"])

    msg = str(exc.value)
    assert "preflight" in msg.lower()
    assert "unsupported_runtime_kind" in msg

    # Verify the event log was written.
    from workflows.code_review.paths import runtime_paths

    event_log_path = runtime_paths(workflow_root)["event_log_path"]
    assert event_log_path.exists(), f"event log not created at {event_log_path}"
    lines = [
        json.loads(line)
        for line in event_log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    skipped = [e for e in lines if e.get("event") == "daedalus.dispatch_skipped"]
    assert len(skipped) == 1, f"expected 1 dispatch_skipped event, got {lines}"
    ev = skipped[0]
    assert ev["code"] == "unsupported_runtime_kind"
    assert ev["workflow"] == "preflight-wf"
    assert "totally-bogus" in (ev.get("detail") or "")
