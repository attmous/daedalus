import json
from pathlib import Path

from workflows.contract import render_workflow_markdown


def _config(tmp_path: Path) -> dict:
    return {
        "workflow": "issue-runner",
        "schema-version": 1,
        "instance": {"name": "attmous-daedalus-issue-runner", "engine-owner": "hermes"},
        "repository": {"local-path": str(tmp_path / "repo"), "github-slug": "attmous/daedalus"},
        "tracker": {
            "kind": "local-json",
            "path": "config/issues.json",
            "active-states": ["todo"],
            "terminal-states": ["done"],
        },
        "workspace": {"root": "workspace/issues"},
        "hooks": {
            "after-create": "echo created > created.txt",
            "before-run": "echo before > before.txt",
            "after-run": "echo after > after.txt",
            "timeout-seconds": 10,
        },
        "runtimes": {
            "default": {
                "kind": "hermes-agent",
                "command": ["fake-agent", "--prompt", "{prompt_path}", "--issue", "{issue_id}"],
            }
        },
        "agent": {
            "name": "Issue_Runner_Agent",
            "model": "gpt-5.4",
            "runtime": "default",
        },
        "storage": {
            "status": "memory/workflow-status.json",
            "health": "memory/workflow-health.json",
            "audit-log": "memory/workflow-audit.jsonl",
        },
    }


def test_issue_runner_tick_runs_selected_issue_and_writes_artifacts(tmp_path):
    from workflows.issue_runner.workspace import load_workspace_from_config

    cfg = _config(tmp_path)
    workflow_root = tmp_path / "attmous-daedalus-issue-runner"
    workflow_root.mkdir()
    (workflow_root / "config").mkdir()
    (workflow_root / "config" / "issues.json").write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "id": "ISSUE-1",
                        "title": "First issue",
                        "description": "Do the thing.",
                        "state": "todo",
                        "labels": ["sample"],
                    },
                    {
                        "id": "ISSUE-2",
                        "title": "Done issue",
                        "description": "Already done.",
                        "state": "done",
                        "labels": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (workflow_root / "WORKFLOW.md").write_text(
        render_workflow_markdown(config=cfg, prompt_template="Work the issue carefully."),
        encoding="utf-8",
    )

    def fake_run(command, *, cwd=None, timeout=None, env=None):
        if command[:2] == ["bash", "-lc"] and cwd is not None:
            script = command[2]
            if "created.txt" in script:
                (cwd / "created.txt").write_text("created\n", encoding="utf-8")
            if "before.txt" in script:
                (cwd / "before.txt").write_text("before\n", encoding="utf-8")
            if "after.txt" in script:
                (cwd / "after.txt").write_text("after\n", encoding="utf-8")

        class Result:
            stdout = "agent finished\n"
            stderr = ""
            returncode = 0

        return Result()

    workspace = load_workspace_from_config(
        workspace_root=workflow_root,
        run=fake_run,
        run_json=lambda *args, **kwargs: {},
    )

    result = workspace.tick()

    assert result["ok"] is True
    assert result["selectedIssue"]["id"] == "ISSUE-1"
    output_path = Path(result["outputPath"])
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "agent finished\n"
    issue_workspace = Path(result["workspace"])
    assert (issue_workspace / "created.txt").exists()
    assert (issue_workspace / "before.txt").exists()
    assert (issue_workspace / "after.txt").exists()
    status = workspace.build_status()
    assert status["selectedIssue"]["id"] == "ISSUE-1"
    assert status["tracker"]["eligibleCount"] == 1
