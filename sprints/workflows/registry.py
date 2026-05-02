"""Workflow registry and CLI dispatch."""

from __future__ import annotations

import importlib
import inspect
import json
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, runtime_checkable

import jsonschema
import yaml

from workflows.config import AgenticConfig
from workflows.contracts import WorkflowContractError, load_workflow_contract
from workflows.paths import runtime_paths

NAME = "agentic"
SUPPORTED_SCHEMA_VERSIONS = (1,)
CONFIG_SCHEMA_PATH = Path(__file__).with_name("schema.yaml")
PREFLIGHT_GATED_COMMANDS = frozenset()


@runtime_checkable
class Workflow(Protocol):
    name: str
    schema_versions: tuple[int, ...]
    schema_path: Path
    preflight_gated_commands: frozenset[str]

    def load_config(self, *, workflow_root: Path, raw: dict[str, Any]) -> object: ...

    def make_workspace(self, *, workflow_root: Path, config: object) -> object: ...

    def run_cli(self, *, workspace: object, argv: list[str]) -> int: ...

    def run_preflight(self, *, workflow_root: Path, config: object) -> object: ...


@dataclass(frozen=True)
class ModuleWorkflow:
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
        signature = inspect.signature(preflight)
        if "workflow_root" in signature.parameters:
            return preflight(raw, workflow_root=workflow_root)
        return preflight(raw)


@dataclass(frozen=True)
class AgenticWorkflow:
    name: str = NAME
    schema_versions: tuple[int, ...] = SUPPORTED_SCHEMA_VERSIONS
    schema_path: Path = CONFIG_SCHEMA_PATH
    preflight_gated_commands: frozenset[str] = PREFLIGHT_GATED_COMMANDS

    def load_config(self, *, workflow_root: Path, raw: dict[str, Any]) -> object:
        return load_config(workflow_root=workflow_root, raw=raw)

    def make_workspace(self, *, workflow_root: Path, config: object) -> object:
        return make_workspace(workflow_root=workflow_root, config=config)

    def run_cli(self, *, workspace: object, argv: list[str]) -> int:
        from workflows.runner import main

        return main(workspace, argv)

    def run_preflight(self, *, workflow_root: Path, config: object) -> object:
        del workflow_root, config
        return type("PreflightResult", (), {"ok": True})()

def load_config(*, workflow_root: Path, raw: dict[str, Any]) -> AgenticConfig:
    return AgenticConfig.from_raw(raw=raw, workflow_root=workflow_root)

def make_workspace(*, workflow_root: Path, config: object) -> AgenticConfig:
    if isinstance(config, AgenticConfig):
        return config
    if isinstance(config, dict):
        return AgenticConfig.from_raw(raw=config, workflow_root=workflow_root)
    raise TypeError(f"unsupported agentic config object: {type(config).__name__}")

def load_workflow(name: str) -> ModuleType:
    workflow = load_workflow_object(name)
    module = _import_workflow_module(name)
    if module.NAME != workflow.name:
        raise WorkflowContractError(
            f"workflow module for {name!r} declares NAME={module.NAME!r}, expected {workflow.name!r}"
        )
    return module

def load_workflow_object(name: str) -> Workflow:
    if name == NAME:
        return WORKFLOW
    module = _import_workflow_module(name)
    workflow = getattr(module, "WORKFLOW", None) or ModuleWorkflow(module)
    if workflow.name != name:
        raise WorkflowContractError(
            f"workflow module for {name!r} declares NAME={workflow.name!r}"
        )
    return workflow

def run_cli(
    workflow_root: Path, argv: list[str], *, require_workflow: str | None = None
) -> int:
    contract = load_workflow_contract(workflow_root)
    raw_config = contract.config
    workflow_name = raw_config.get("workflow")
    if not workflow_name:
        raise WorkflowContractError(
            f"{contract.source_path} is missing top-level `workflow:` field"
        )
    if require_workflow and workflow_name != require_workflow:
        raise WorkflowContractError(
            f"{contract.source_path} declares workflow={workflow_name!r}, "
            f"but invocation pins require_workflow={require_workflow!r}"
        )
    workflow = load_workflow_object(str(workflow_name))
    schema = yaml.safe_load(workflow.schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(raw_config, schema)
    schema_version = int(raw_config.get("schema-version", 1))
    if schema_version not in workflow.schema_versions:
        raise WorkflowContractError(
            f"workflow {workflow_name!r} does not support schema-version={schema_version}; "
            f"supported: {list(workflow.schema_versions)}"
        )
    config = workflow.load_config(workflow_root=workflow_root, raw=raw_config)
    invoked_command = argv[0] if argv else None
    if invoked_command in workflow.preflight_gated_commands:
        result = workflow.run_preflight(workflow_root=workflow_root, config=config)
        if not getattr(result, "ok", True):
            _emit_dispatch_skipped_event(
                workflow_root=workflow_root,
                workflow_name=str(workflow_name),
                error_code=getattr(result, "error_code", None),
                error_detail=getattr(result, "error_detail", None),
            )
            raise WorkflowContractError(
                f"dispatch preflight failed for workflow {workflow_name!r}: "
                f"code={getattr(result, 'error_code', None)} detail={getattr(result, 'error_detail', None)}"
            )
    workspace = workflow.make_workspace(workflow_root=workflow_root, config=config)
    return workflow.run_cli(workspace=workspace, argv=argv)

def list_workflows() -> list[str]:
    return [NAME]

def _import_workflow_module(name: str) -> ModuleType:
    if name == NAME:
        return importlib.import_module("workflows")
    return importlib.import_module(f"workflows.{name.replace('-', '_')}")

def _emit_dispatch_skipped_event(
    *,
    workflow_root: Path,
    workflow_name: str,
    error_code: str | None,
    error_detail: str | None,
) -> None:
    try:
        from workflows.paths import runtime_paths
        import runtime as _runtime

        paths = runtime_paths(workflow_root)
        _runtime.append_sprints_event(
            event_log_path=paths["event_log_path"],
            event={
                "event": "sprints.dispatch_skipped",
                "workflow": workflow_name,
                "code": error_code,
                "detail": error_detail,
            },
        )
    except Exception:
        pass

WORKFLOW = AgenticWorkflow()
