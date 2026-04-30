"""Runtime abstractions shared by bundled workflows."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SessionHandle:
    record_id: str | None
    session_id: str | None
    name: str


@dataclass(frozen=True)
class SessionHealth:
    healthy: bool
    reason: str | None
    last_used_at: str | None


@runtime_checkable
class Runtime(Protocol):
    def ensure_session(
        self,
        *,
        worktree: Path,
        session_name: str,
        model: str,
        resume_session_id: str | None = None,
    ) -> SessionHandle: ...

    def run_prompt(
        self,
        *,
        worktree: Path,
        session_name: str,
        prompt: str,
        model: str,
    ) -> str: ...

    def assess_health(
        self,
        session_meta: dict | None,
        *,
        worktree: Path | None,
        now_epoch: int | None = None,
    ) -> SessionHealth: ...

    def close_session(
        self,
        *,
        worktree: Path,
        session_name: str,
    ) -> None: ...

    def run_command(
        self,
        *,
        worktree: Path,
        command_argv: list[str],
        env: dict[str, str] | None = None,
    ) -> str: ...

    def last_activity_ts(self) -> float | None: ...


_RUNTIME_KINDS: dict[str, type] = {}


def register(kind: str):
    def _register(cls):
        _RUNTIME_KINDS[kind] = cls
        return cls

    return _register


def build_runtimes(runtimes_cfg: dict, *, run=None, run_json=None) -> dict[str, Runtime]:
    if not runtimes_cfg:
        return {}

    from workflows.shared.runtimes import acpx_codex  # noqa: F401
    from workflows.shared.runtimes import claude_cli  # noqa: F401
    from workflows.shared.runtimes import hermes_agent  # noqa: F401

    out: dict[str, Runtime] = {}
    for profile_name, profile_cfg in runtimes_cfg.items():
        kind = profile_cfg.get("kind")
        if kind not in _RUNTIME_KINDS:
            raise ValueError(
                f"runtime profile {profile_name!r} declares unknown kind={kind!r}; "
                f"registered kinds: {sorted(_RUNTIME_KINDS)}"
            )
        cls = _RUNTIME_KINDS[kind]
        out[profile_name] = cls(profile_cfg, run=run, run_json=run_json)
    return out

