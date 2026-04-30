from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_SLUG_RE = re.compile(r"[^a-z0-9]+")


class TrackerConfigError(RuntimeError):
    """Raised when the tracker section is missing or invalid."""


def resolve_tracker_path(*, workflow_root: Path, tracker_cfg: dict[str, Any]) -> Path:
    path_value = str(tracker_cfg.get("path") or "").strip()
    if not path_value:
        raise TrackerConfigError("tracker.path is required")
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = (workflow_root / path).resolve()
    return path


def load_issues(*, workflow_root: Path, tracker_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    kind = str(tracker_cfg.get("kind") or "").strip()
    if kind != "local-json":
        raise TrackerConfigError(f"unsupported tracker.kind={kind!r}; issue-runner currently supports only 'local-json'")
    path = resolve_tracker_path(workflow_root=workflow_root, tracker_cfg=tracker_cfg)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        raw_issues = payload.get("issues")
    else:
        raw_issues = payload
    if not isinstance(raw_issues, list):
        raise TrackerConfigError(f"{path} must contain a top-level list or an object with an 'issues' list")
    return [_normalize_issue(item) for item in raw_issues]


def select_issue(*, tracker_cfg: dict[str, Any], issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    active_states = {str(value).strip().lower() for value in (tracker_cfg.get("active-states") or []) if str(value).strip()}
    terminal_states = {
        str(value).strip().lower()
        for value in (tracker_cfg.get("terminal-states") or ["done", "closed", "canceled", "cancelled", "resolved"])
        if str(value).strip()
    }
    required_labels = {str(value).strip().lower() for value in (tracker_cfg.get("required-labels") or []) if str(value).strip()}
    exclude_labels = {str(value).strip().lower() for value in (tracker_cfg.get("exclude-labels") or []) if str(value).strip()}

    for issue in issues:
        state = str(issue.get("state") or "").strip().lower()
        labels = {str(label).strip().lower() for label in (issue.get("labels") or []) if str(label).strip()}
        if state and state in terminal_states:
            continue
        if active_states and state not in active_states:
            continue
        if required_labels and not required_labels.issubset(labels):
            continue
        if exclude_labels and labels.intersection(exclude_labels):
            continue
        return issue
    return None


def issue_workspace_slug(issue: dict[str, Any]) -> str:
    issue_id = str(issue.get("id") or "issue").strip().lower()
    title = str(issue.get("title") or issue_id).strip().lower()
    raw = f"{issue_id}-{title}"
    return _SLUG_RE.sub("-", raw).strip("-") or "issue"


def issue_session_name(issue: dict[str, Any]) -> str:
    return issue_workspace_slug(issue)[:64]


def _normalize_issue(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TrackerConfigError(f"issue entries must be objects, got {type(payload).__name__}")
    issue_id = str(payload.get("id") or "").strip()
    if not issue_id:
        raise TrackerConfigError("each issue entry must define a non-empty id")
    title = str(payload.get("title") or issue_id).strip()
    description = str(payload.get("description") or "").strip()
    state = str(payload.get("state") or "").strip()
    labels_raw = payload.get("labels") or []
    if not isinstance(labels_raw, list):
        raise TrackerConfigError(f"issue {issue_id!r} labels must be a list")
    labels = [str(label).strip() for label in labels_raw if str(label).strip()]
    return {
        "id": issue_id,
        "title": title,
        "description": description,
        "state": state,
        "labels": labels,
    }

