from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workflows.issue_runner.tracker import TrackerConfigError, resolve_tracker_path


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    error_code: str | None = None
    error_detail: str | None = None


def run_preflight(config: dict[str, Any]) -> PreflightResult:
    try:
        _validate_config(config)
    except RuntimeError as exc:
        return PreflightResult(ok=False, error_code="invalid-config", error_detail=str(exc))
    return PreflightResult(ok=True)


def _validate_config(config: dict[str, Any]) -> None:
    runtimes = config.get("runtimes") or {}
    agent = config.get("agent") or {}
    runtime_name = str(agent.get("runtime") or "").strip()
    if not runtime_name:
        raise RuntimeError("agent.runtime is required")
    if runtime_name not in runtimes:
        raise RuntimeError(f"agent.runtime={runtime_name!r} does not reference a declared runtime profile")
    runtime_cfg = runtimes.get(runtime_name) or {}
    runtime_kind = str(runtime_cfg.get("kind") or "").strip()
    if runtime_kind == "hermes-agent":
        if not (agent.get("command") or runtime_cfg.get("command")):
            raise RuntimeError(
                "hermes-agent runtime requires command on the runtime profile or agent block"
            )

    workflow_root = Path(".")
    tracker_cfg = config.get("tracker") or {}
    try:
        resolve_tracker_path(workflow_root=workflow_root, tracker_cfg=tracker_cfg)
    except TrackerConfigError as exc:
        raise RuntimeError(str(exc)) from exc

