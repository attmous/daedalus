from pathlib import Path

import jsonschema
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _config() -> dict:
    return {
        "workflow": "issue-runner",
        "schema-version": 1,
        "instance": {"name": "attmous-daedalus-issue-runner", "engine-owner": "hermes"},
        "repository": {"local-path": "/tmp/repo", "github-slug": "attmous/daedalus"},
        "tracker": {
            "kind": "local-json",
            "path": "config/issues.json",
            "active-states": ["todo"],
            "terminal-states": ["done"],
        },
        "workspace": {"root": "workspace/issues"},
        "runtimes": {
            "default": {
                "kind": "claude-cli",
                "max-turns-per-invocation": 8,
                "timeout-seconds": 60,
            }
        },
        "agent": {"name": "runner", "model": "claude-sonnet-4-6", "runtime": "default"},
        "storage": {
            "status": "memory/workflow-status.json",
            "health": "memory/workflow-health.json",
            "audit-log": "memory/workflow-audit.jsonl",
        },
    }


def test_issue_runner_schema_accepts_minimal_valid_config():
    schema = yaml.safe_load(
        (REPO_ROOT / "daedalus" / "workflows" / "issue_runner" / "schema.yaml").read_text(encoding="utf-8")
    )
    jsonschema.validate(_config(), schema)


def test_issue_runner_schema_rejects_wrong_workflow_name():
    schema = yaml.safe_load(
        (REPO_ROOT / "daedalus" / "workflows" / "issue_runner" / "schema.yaml").read_text(encoding="utf-8")
    )
    cfg = _config()
    cfg["workflow"] = "change-delivery"
    try:
        jsonschema.validate(cfg, schema)
    except jsonschema.ValidationError:
        return
    raise AssertionError("expected schema validation error for wrong workflow name")

