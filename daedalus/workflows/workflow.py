"""Standard workflow object contract."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Workflow(Protocol):
    name: str
    schema_versions: tuple[int, ...]
    schema_path: Path
    preflight_gated_commands: frozenset[str]

    def load_config(self, *, workflow_root: Path, raw: dict[str, Any]) -> object:
        ...

    def make_workspace(self, *, workflow_root: Path, config: object) -> object:
        ...

    def run_cli(self, *, workspace: object, argv: list[str]) -> int:
        ...

    def run_preflight(self, *, workflow_root: Path, config: object) -> object:
        ...


@dataclass(frozen=True)
class ModuleWorkflow:
    """Adapter for existing workflow packages during the class migration."""

    module: ModuleType

    @property
    def name(self) -> str:
        return self.module.NAME

    @property
    def schema_versions(self) -> tuple[int, ...]:
        return tuple(self.module.SUPPORTED_SCHEMA_VERSIONS)

    @property
    def schema_path(self) -> Path:
        return Path(self.module.CONFIG_SCHEMA_PATH)

    @property
    def preflight_gated_commands(self) -> frozenset[str]:
        return frozenset(getattr(self.module, "PREFLIGHT_GATED_COMMANDS", frozenset()))

    def load_config(self, *, workflow_root: Path, raw: dict[str, Any]) -> object:
        loader = getattr(self.module, "load_config", None)
        if callable(loader):
            return loader(workflow_root=workflow_root, raw=raw)
        return raw

    def make_workspace(self, *, workflow_root: Path, config: object) -> object:
        raw = config.raw if hasattr(config, "raw") else config
        return self.module.make_workspace(workflow_root=workflow_root, config=raw)

    def run_cli(self, *, workspace: object, argv: list[str]) -> int:
        return self.module.cli_main(workspace, argv)

    def run_preflight(self, *, workflow_root: Path, config: object) -> object:
        preflight = getattr(self.module, "run_preflight", None)
        if not callable(preflight):
            return type("PreflightResult", (), {"ok": True})()
        raw = config.raw if hasattr(config, "raw") else config
        try:
            return preflight(raw, workflow_root=workflow_root)
        except TypeError:
            return preflight(raw)
