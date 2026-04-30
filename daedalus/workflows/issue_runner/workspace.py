from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from workflows.contract import WORKFLOW_POLICY_KEY, load_workflow_contract
from workflows.shared.config_snapshot import AtomicRef, ConfigSnapshot
from workflows.shared.runtimes import Runtime, build_runtimes
from workflows.issue_runner.tracker import (
    TrackerConfigError,
    issue_session_name,
    issue_workspace_slug,
    load_issues,
    resolve_tracker_path,
    select_issue,
)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _render_prompt(*, workflow_policy: str, issue: dict[str, Any], attempt: int) -> str:
    sections = []
    if workflow_policy.strip():
        sections.append(workflow_policy.strip())
    sections.append(
        "\n".join(
            [
                "# Issue",
                f"- id: {issue.get('id')}",
                f"- title: {issue.get('title')}",
                f"- state: {issue.get('state') or 'unknown'}",
                f"- labels: {', '.join(issue.get('labels') or []) or 'none'}",
                f"- attempt: {attempt}",
                "",
                "## Description",
                str(issue.get("description") or "").strip() or "No description provided.",
            ]
        )
    )
    return "\n\n".join(sections).strip() + "\n"


def _subprocess_run(command: list[str], *, cwd: Path | None = None, timeout: int | None = None, env: dict[str, str] | None = None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=merged_env,
    )


def _subprocess_run_json(command: list[str], *, cwd: Path | None = None, timeout: int | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    completed = _subprocess_run(command, cwd=cwd, timeout=timeout, env=env)
    payload = json.loads(completed.stdout or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError("expected JSON object payload")
    return payload


@dataclass
class IssueRunnerWorkspace:
    path: Path
    config: dict[str, Any]
    snapshot_ref: AtomicRef[ConfigSnapshot]
    contract_path: Path
    tracker_path: Path
    issue_workspace_root: Path
    status_path: Path
    health_path: Path
    audit_log_path: Path
    runtimes: dict[str, Runtime]
    _run: Callable[..., Any]
    _run_json: Callable[..., dict[str, Any]]

    def runtime(self, name: str) -> Runtime:
        return self.runtimes[name]

    def build_status(self) -> dict[str, Any]:
        snapshot = self.snapshot_ref.get()
        tracker_cfg = snapshot.config.get("tracker") or {}
        try:
            issues = load_issues(workflow_root=self.path, tracker_cfg=tracker_cfg)
            selected = select_issue(tracker_cfg=tracker_cfg, issues=issues)
            eligible_count = sum(
                1 for issue in issues if select_issue(tracker_cfg=tracker_cfg, issues=[issue]) is not None
            )
            health = "healthy"
            error = None
        except Exception as exc:
            issues = []
            selected = None
            eligible_count = 0
            health = "error"
            error = f"{type(exc).__name__}: {exc}"
        last_run = _load_optional_json(self.status_path)
        return {
            "workflow": "issue-runner",
            "source": "issue-runner",
            "workflowRoot": str(self.path),
            "contractPath": str(self.contract_path),
            "health": health,
            "error": error,
            "tracker": {
                "kind": tracker_cfg.get("kind"),
                "path": str(self.tracker_path),
                "issueCount": len(issues),
                "eligibleCount": eligible_count,
            },
            "selectedIssue": selected,
            "workspaceRoot": str(self.issue_workspace_root),
            "lastRun": (last_run or {}).get("lastRun"),
            "updatedAt": _now_iso(),
        }

    def doctor(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        try:
            issues = load_issues(workflow_root=self.path, tracker_cfg=self.config.get("tracker") or {})
            checks.append({"name": "tracker", "status": "pass", "detail": f"{len(issues)} issue(s) loaded"})
        except Exception as exc:
            checks.append({"name": "tracker", "status": "fail", "detail": str(exc)})

        try:
            self.issue_workspace_root.mkdir(parents=True, exist_ok=True)
            checks.append({"name": "workspace-root", "status": "pass", "detail": str(self.issue_workspace_root)})
        except OSError as exc:
            checks.append({"name": "workspace-root", "status": "fail", "detail": str(exc)})

        agent_cfg = self.config.get("agent") or {}
        runtime_name = str(agent_cfg.get("runtime") or "")
        if runtime_name and runtime_name in self.runtimes:
            checks.append({"name": "agent-runtime", "status": "pass", "detail": runtime_name})
        else:
            checks.append({"name": "agent-runtime", "status": "fail", "detail": f"unknown runtime {runtime_name!r}"})

        ok = all(check["status"] == "pass" for check in checks)
        return {
            "ok": ok,
            "workflow": "issue-runner",
            "checks": checks,
            "updatedAt": _now_iso(),
        }

    def tick(self) -> dict[str, Any]:
        status = {
            "ok": False,
            "workflow": "issue-runner",
            "updatedAt": _now_iso(),
            "selectedIssue": None,
            "attempt": None,
            "outputPath": None,
        }
        tracker_cfg = self.config.get("tracker") or {}
        issues = load_issues(workflow_root=self.path, tracker_cfg=tracker_cfg)
        selected = select_issue(tracker_cfg=tracker_cfg, issues=issues)
        status["selectedIssue"] = selected
        if selected is None:
            status["ok"] = True
            status["message"] = "no eligible issues"
            self._write_status(status, health="healthy")
            self._emit_event("issue_runner.tick.noop", {"reason": "no-eligible-issues"})
            return status

        issue_workspace = self.issue_workspace_root / issue_workspace_slug(selected)
        issue_workspace.mkdir(parents=True, exist_ok=True)
        daemon_dir = issue_workspace / ".daedalus"
        daemon_dir.mkdir(parents=True, exist_ok=True)
        created_workspace = not (daemon_dir / "created.marker").exists()
        if created_workspace:
            (daemon_dir / "created.marker").write_text(_now_iso() + "\n", encoding="utf-8")

        last_run = (_load_optional_json(self.status_path) or {}).get("lastRun") or {}
        attempt = int(last_run.get("attempt") or 0) + 1 if (last_run.get("issue") or {}).get("id") == selected.get("id") else 1
        status["attempt"] = attempt

        prompt = _render_prompt(
            workflow_policy=str(self.config.get(WORKFLOW_POLICY_KEY) or ""),
            issue=selected,
            attempt=attempt,
        )
        prompt_path = daemon_dir / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        output_path = daemon_dir / "last-output.txt"
        status["outputPath"] = str(output_path)

        env = self._hook_env(issue=selected, issue_workspace=issue_workspace, prompt_path=prompt_path, output_path=output_path)
        hook_results: list[dict[str, Any]] = []

        if created_workspace:
            hook_results.append(self._run_hook("after-create", issue_workspace, env))
        hook_results.append(self._run_hook("before-run", issue_workspace, env))

        agent_cfg = self.config.get("agent") or {}
        runtime_cfg = (self.config.get("runtimes") or {}).get(agent_cfg.get("runtime")) or {}
        runtime = self.runtime(str(agent_cfg.get("runtime")))
        session_name = issue_session_name(selected)
        model = str(agent_cfg.get("model") or "")
        runtime.ensure_session(worktree=issue_workspace, session_name=session_name, model=model)

        command = agent_cfg.get("command") or runtime_cfg.get("command")
        if command:
            argv = self._render_command(
                command=command,
                worktree=issue_workspace,
                model=model,
                session_name=session_name,
                prompt_path=prompt_path,
                issue=selected,
            )
            output = runtime.run_command(worktree=issue_workspace, command_argv=argv, env=env)
        else:
            output = runtime.run_prompt(
                worktree=issue_workspace,
                session_name=session_name,
                prompt=prompt,
                model=model,
            )
        output_path.write_text(output, encoding="utf-8")
        hook_results.append(self._run_hook("after-run", issue_workspace, env))

        status.update(
            {
                "ok": True,
                "workspace": str(issue_workspace),
                "createdWorkspace": created_workspace,
                "hookResults": hook_results,
            }
        )
        self._write_status(status, health="healthy")
        self._emit_event(
            "issue_runner.tick.completed",
            {
                "issue_id": selected.get("id"),
                "attempt": attempt,
                "workspace": str(issue_workspace),
                "output_path": str(output_path),
            },
        )
        return status

    def _write_status(self, tick_result: dict[str, Any], *, health: str) -> None:
        payload = {
            "workflow": "issue-runner",
            "health": health,
            "lastRun": {
                "ok": tick_result.get("ok"),
                "issue": tick_result.get("selectedIssue"),
                "attempt": tick_result.get("attempt"),
                "outputPath": tick_result.get("outputPath"),
                "updatedAt": tick_result.get("updatedAt") or _now_iso(),
            },
        }
        _write_json(self.status_path, payload)
        _write_json(
            self.health_path,
            {
                "workflow": "issue-runner",
                "health": health,
                "updatedAt": payload["lastRun"]["updatedAt"],
            },
        )

    def _emit_event(self, event: str, payload: dict[str, Any]) -> None:
        _append_jsonl(
            self.audit_log_path,
            {"event": event, "at": _now_iso(), **payload},
        )

    def _hook_env(
        self,
        *,
        issue: dict[str, Any],
        issue_workspace: Path,
        prompt_path: Path,
        output_path: Path,
    ) -> dict[str, str]:
        repository_cfg = self.config.get("repository") or {}
        return {
            "WORKFLOW_ROOT": str(self.path),
            "ISSUE_ID": str(issue.get("id") or ""),
            "ISSUE_TITLE": str(issue.get("title") or ""),
            "ISSUE_STATE": str(issue.get("state") or ""),
            "ISSUE_LABELS": ",".join(issue.get("labels") or []),
            "ISSUE_WORKSPACE": str(issue_workspace),
            "PROMPT_PATH": str(prompt_path),
            "OUTPUT_PATH": str(output_path),
            "REPOSITORY_PATH": str(repository_cfg.get("local-path") or ""),
        }

    def _run_hook(self, hook_name: str, worktree: Path, env: dict[str, str]) -> dict[str, Any]:
        hooks_cfg = self.config.get("hooks") or {}
        script = str(hooks_cfg.get(hook_name) or "").strip()
        if not script:
            return {"hook": hook_name, "ran": False}
        timeout = int(hooks_cfg.get("timeout-seconds") or 60)
        completed = self._run(["bash", "-lc", script], cwd=worktree, timeout=timeout, env=env)
        return {
            "hook": hook_name,
            "ran": True,
            "returncode": getattr(completed, "returncode", 0),
        }

    def _render_command(
        self,
        *,
        command: Any,
        worktree: Path,
        model: str,
        session_name: str,
        prompt_path: Path,
        issue: dict[str, Any],
    ) -> list[str]:
        if not isinstance(command, list) or not command:
            raise RuntimeError("agent.command and runtime command must be a non-empty argv list")
        fmt = {
            "worktree": str(worktree),
            "model": model,
            "session_name": session_name,
            "prompt_path": str(prompt_path),
            "issue_id": str(issue.get("id") or ""),
            "issue_title": str(issue.get("title") or ""),
            "workflow_root": str(self.path),
        }
        return [str(part).format(**fmt) for part in command]


def load_workspace_from_config(
    *,
    workspace_root: Path,
    config: dict[str, Any] | None = None,
    run: Callable[..., Any] | None = None,
    run_json: Callable[..., dict[str, Any]] | None = None,
) -> IssueRunnerWorkspace:
    root = workspace_root.expanduser().resolve()
    contract = load_workflow_contract(root)
    cfg = dict(config or contract.config)
    prompts = cfg.get("prompts") or {}
    st = contract.source_path.stat()
    snapshot = ConfigSnapshot(
        config=cfg,
        prompts=prompts,
        loaded_at=time.monotonic(),
        source_mtime=st.st_mtime,
        source_size=st.st_size,
    )
    tracker_cfg = cfg.get("tracker") or {}
    workspace_cfg = cfg.get("workspace") or {}
    storage_cfg = cfg.get("storage") or {}

    def _resolve_path(value: str, default: str) -> Path:
        raw = str(value or default).strip()
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (root / path).resolve()
        return path

    tracker_path = resolve_tracker_path(workflow_root=root, tracker_cfg=tracker_cfg)
    issue_workspace_root = _resolve_path(workspace_cfg.get("root") or "workspace/issues", "workspace/issues")
    status_path = _resolve_path(storage_cfg.get("status") or "memory/workflow-status.json", "memory/workflow-status.json")
    health_path = _resolve_path(storage_cfg.get("health") or "memory/workflow-health.json", "memory/workflow-health.json")
    audit_log_path = _resolve_path(storage_cfg.get("audit-log") or "memory/workflow-audit.jsonl", "memory/workflow-audit.jsonl")

    runner = run or _subprocess_run
    runner_json = run_json or _subprocess_run_json
    runtimes = build_runtimes(cfg.get("runtimes") or {}, run=runner, run_json=runner_json)

    return IssueRunnerWorkspace(
        path=root,
        config=cfg,
        snapshot_ref=AtomicRef(snapshot),
        contract_path=contract.source_path,
        tracker_path=tracker_path,
        issue_workspace_root=issue_workspace_root,
        status_path=status_path,
        health_path=health_path,
        audit_log_path=audit_log_path,
        runtimes=runtimes,
        _run=runner,
        _run_json=runner_json,
    )


def make_workspace(*, workflow_root: Path, config: dict) -> IssueRunnerWorkspace:
    return load_workspace_from_config(workspace_root=workflow_root, config=config)

