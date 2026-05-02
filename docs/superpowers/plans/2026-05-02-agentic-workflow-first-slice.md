# Agentic Workflow First Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first usable `workflow: agentic` path where `WORKFLOW.md` defines stages, gates, actors, actions, and policy, while Python keeps only loading, validation, execution mechanics, and state persistence.

**Architecture:** Create `daedalus/workflows/agentic/` as a new clean workflow package next to legacy `issue_runner/` and `change_delivery/`. The first slice supports front matter config, policy chunk parsing, prompt rendering, typed state, orchestrator decision validation, actor/action mechanics, and a CLI that can validate or tick a minimal workflow with deterministic/local runtime options.

**Tech Stack:** Python 3.10+, dataclasses, Protocols, PyYAML, jsonschema, existing `workflows.registry`, `workflows.contract`, and `workflows.prompts`.

**Verification Policy:** Do not create new tests in this wave. Do not add `tests/` files. Verify with import checks, CLI help, workflow validation, and a minimal smoke workflow using temporary local files.

---

## File Structure

Create:

- `daedalus/workflows/agentic/__init__.py` - standard workflow object for `workflow: agentic`.
- `daedalus/workflows/agentic/workflow_object.py` - concrete workflow class using the standard workflow object methods.
- `daedalus/workflows/agentic/schema.yaml` - mechanical schema for the front matter contract.
- `daedalus/workflows/agentic/config.py` - typed dataclasses for workflow config and section references.
- `daedalus/workflows/agentic/contract.py` - parse `WORKFLOW.md` into front matter plus orchestrator and actor policy chunks.
- `daedalus/workflows/agentic/state.py` - small generic durable state and JSON storage helpers.
- `daedalus/workflows/agentic/prompts.py` - prompt builders for orchestrator and actor runs.
- `daedalus/workflows/agentic/orchestrator.py` - decision dataclass and JSON validation.
- `daedalus/workflows/agentic/actors.py` - actor runtime abstraction and local deterministic runtime.
- `daedalus/workflows/agentic/actions.py` - action registry with `noop`, `command`, and `comment`.
- `daedalus/workflows/agentic/stages.py` - stage execution helpers that run actors and actions mechanically.
- `daedalus/workflows/agentic/gates.py` - gate validation helpers for orchestrator-evaluated gates.
- `daedalus/workflows/agentic/cli.py` - `validate`, `show`, and `tick` commands.
- `daedalus/workflows/agentic/__main__.py` - direct package entrypoint.
- `daedalus/workflows/agentic/workflow.template.md` - minimal working template.

Modify:

- `daedalus/workflows/README.md` - document that `agentic/` is the clean replacement path while legacy folders stay until parity.
- `docs/workflows/README.md` - add a short note about `workflow: agentic`.

Do not modify:

- `daedalus/workflows/issue_runner/`
- `daedalus/workflows/change_delivery/`
- `tests/`

---

### Task 1: Add Agentic Package Shell

**Files:**
- Create: `daedalus/workflows/agentic/__init__.py`
- Create: `daedalus/workflows/agentic/workflow_object.py`
- Create: `daedalus/workflows/agentic/__main__.py`
- Create: `daedalus/workflows/agentic/schema.yaml`
- Create: `daedalus/workflows/agentic/workflow.template.md`

- [ ] **Step 1: Create `__init__.py` with a standard workflow object**

Use a real class instead of `ModuleWorkflow`:

```python
"""Generic agentic workflow package."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from workflows.agentic.cli import main as cli_main
from workflows.agentic.config import AgenticConfig
from workflows.agentic.workflow_object import AgenticWorkflow

NAME = "agentic"
SUPPORTED_SCHEMA_VERSIONS = (1,)
CONFIG_SCHEMA_PATH = Path(__file__).with_name("schema.yaml")
PREFLIGHT_GATED_COMMANDS = frozenset()


def load_config(*, workflow_root: Path, raw: dict[str, Any]) -> AgenticConfig:
    return AgenticConfig.from_raw(raw, workflow_root=workflow_root)


def make_workspace(*, workflow_root: Path, config: object) -> AgenticConfig:
    if isinstance(config, AgenticConfig):
        return config
    if isinstance(config, dict):
        return AgenticConfig.from_raw(config, workflow_root=workflow_root)
    raise TypeError(f"unsupported agentic config object: {type(config).__name__}")


WORKFLOW = AgenticWorkflow(
    name=NAME,
    schema_versions=SUPPORTED_SCHEMA_VERSIONS,
    schema_path=CONFIG_SCHEMA_PATH,
    preflight_gated_commands=PREFLIGHT_GATED_COMMANDS,
    load_config_func=load_config,
    make_workspace_func=make_workspace,
    run_cli_func=cli_main,
)

__all__ = [
    "NAME",
    "SUPPORTED_SCHEMA_VERSIONS",
    "CONFIG_SCHEMA_PATH",
    "PREFLIGHT_GATED_COMMANDS",
    "WORKFLOW",
    "load_config",
    "make_workspace",
    "cli_main",
]
```

- [ ] **Step 2: Create `workflow_object.py`**

```python
"""Workflow object implementation for the agentic workflow."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class AgenticWorkflow:
    name: str
    schema_versions: tuple[int, ...]
    schema_path: Path
    preflight_gated_commands: frozenset[str]
    load_config_func: Callable[..., object]
    make_workspace_func: Callable[..., object]
    run_cli_func: Callable[..., int]

    def load_config(self, *, workflow_root: Path, raw: dict[str, Any]) -> object:
        return self.load_config_func(workflow_root=workflow_root, raw=raw)

    def make_workspace(self, *, workflow_root: Path, config: object) -> object:
        return self.make_workspace_func(workflow_root=workflow_root, config=config)

    def run_cli(self, *, workspace: object, argv: list[str]) -> int:
        return self.run_cli_func(workspace, argv)

    def run_preflight(self, *, workflow_root: Path, config: object) -> object:
        return type("PreflightResult", (), {"ok": True})()
```

- [ ] **Step 3: Create `schema.yaml`**

The schema validates mechanical config only:

```yaml
type: object
required:
  - workflow
  - schema-version
  - orchestrator
  - actors
  - stages
  - gates
properties:
  workflow:
    const: agentic
  schema-version:
    type: integer
    enum: [1]
  instance:
    type: object
    additionalProperties: true
  repository:
    type: object
    additionalProperties: true
  orchestrator:
    type: object
    required: [actor]
    properties:
      actor:
        type: string
    additionalProperties: true
  runtimes:
    type: object
    additionalProperties:
      type: object
      additionalProperties: true
  actors:
    type: object
    additionalProperties:
      type: object
      required: [runtime]
      properties:
        runtime:
          type: string
        model:
          type: string
        mode:
          type: string
      additionalProperties: true
  stages:
    type: object
    additionalProperties:
      type: object
      properties:
        actors:
          type: array
          items:
            type: string
        actions:
          type: array
          items:
            type: string
        gates:
          type: array
          items:
            type: string
        next:
          type: string
      additionalProperties: true
  gates:
    type: object
    additionalProperties:
      type: object
      required: [type]
      properties:
        type:
          enum: [orchestrator-evaluated]
      additionalProperties: true
  actions:
    type: object
    additionalProperties:
      type: object
      required: [type]
      additionalProperties: true
  storage:
    type: object
    additionalProperties: true
additionalProperties: true
```

- [ ] **Step 4: Create direct entrypoint**

`daedalus/workflows/agentic/__main__.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

from workflows.agentic import WORKFLOW, load_config
from workflows.contract import load_workflow_contract


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    workflow_root = Path.cwd()
    contract = load_workflow_contract(workflow_root)
    config = load_config(workflow_root=workflow_root, raw=contract.config)
    return WORKFLOW.run_cli(workspace=config, argv=raw_argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Add minimal template**

`daedalus/workflows/agentic/workflow.template.md`:

````markdown
---
workflow: agentic
schema-version: 1
orchestrator:
  actor: orchestrator
runtimes:
  local:
    kind: local
actors:
  orchestrator:
    runtime: local
  implementer:
    runtime: local
stages:
  entry:
    actors: [implementer]
    actions: [noop.record]
    gates: [entry-complete]
    next: done
gates:
  entry-complete:
    type: orchestrator-evaluated
actions:
  noop.record:
    type: noop
storage:
  state: .daedalus/agentic-state.json
  audit-log: .daedalus/agentic-audit.jsonl
---

# Orchestrator Policy

Decide the next valid workflow transition from the current state and stage.

Return JSON only:

{
  "decision": "complete",
  "stage": "entry",
  "target": null,
  "reason": "minimal template completed",
  "inputs": {},
  "operator_message": null
}

# Actor: implementer

## Input

Current stage: {{ workflow.current_stage }}

## Policy

Return a small structured result for the stage.

## Output

Return JSON only:

{
  "status": "done",
  "summary": "minimal actor completed",
  "artifacts": [],
  "validation": [],
  "next_recommendation": "complete"
}
````

- [ ] **Step 6: Commit package shell**

```bash
git add daedalus/workflows/agentic
git commit -m "feat: add agentic workflow shell"
```

---

### Task 2: Add Typed Config and Policy Parsing

**Files:**
- Create: `daedalus/workflows/agentic/config.py`
- Create: `daedalus/workflows/agentic/contract.py`

- [ ] **Step 1: Create config dataclasses**

`config.py` should define:

```python
"""Typed config for the generic agentic workflow."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class AgenticConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActorConfig:
    name: str
    runtime: str
    model: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StageConfig:
    name: str
    actors: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    gates: tuple[str, ...] = ()
    next_stage: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateConfig:
    name: str
    type: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionConfig:
    name: str
    type: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StorageConfig:
    state_path: Path
    audit_log_path: Path


@dataclass(frozen=True)
class AgenticConfig:
    workflow_root: Path
    raw: dict[str, Any]
    orchestrator_actor: str
    actors: dict[str, ActorConfig]
    stages: dict[str, StageConfig]
    gates: dict[str, GateConfig]
    actions: dict[str, ActionConfig]
    storage: StorageConfig

    @classmethod
    def from_raw(cls, *, raw: dict[str, Any], workflow_root: Path) -> "AgenticConfig":
        root = workflow_root.resolve()
        actors = {
            name: ActorConfig(
                name=name,
                runtime=str(value["runtime"]),
                model=value.get("model"),
                raw=dict(value),
            )
            for name, value in dict(raw.get("actors") or {}).items()
        }
        stages = {
            name: StageConfig(
                name=name,
                actors=tuple(value.get("actors") or ()),
                actions=tuple(value.get("actions") or ()),
                gates=tuple(value.get("gates") or ()),
                next_stage=value.get("next"),
                raw=dict(value),
            )
            for name, value in dict(raw.get("stages") or {}).items()
        }
        gates = {
            name: GateConfig(name=name, type=str(value["type"]), raw=dict(value))
            for name, value in dict(raw.get("gates") or {}).items()
        }
        actions = {
            name: ActionConfig(name=name, type=str(value["type"]), raw=dict(value))
            for name, value in dict(raw.get("actions") or {}).items()
        }
        storage_raw = dict(raw.get("storage") or {})
        state_path = _resolve(root, storage_raw.get("state", ".daedalus/agentic-state.json"))
        audit_log_path = _resolve(root, storage_raw.get("audit-log", ".daedalus/agentic-audit.jsonl"))
        orchestrator_actor = str(dict(raw.get("orchestrator") or {}).get("actor", ""))
        config = cls(
            workflow_root=root,
            raw=dict(raw),
            orchestrator_actor=orchestrator_actor,
            actors=actors,
            stages=stages,
            gates=gates,
            actions=actions,
            storage=StorageConfig(state_path=state_path, audit_log_path=audit_log_path),
        )
        config.validate_references()
        return config

    def validate_references(self) -> None:
        if self.orchestrator_actor not in self.actors:
            raise AgenticConfigError(f"unknown orchestrator actor: {self.orchestrator_actor}")
        for stage in self.stages.values():
            for actor in stage.actors:
                if actor not in self.actors:
                    raise AgenticConfigError(f"stage {stage.name} references unknown actor {actor}")
            for gate in stage.gates:
                if gate not in self.gates:
                    raise AgenticConfigError(f"stage {stage.name} references unknown gate {gate}")
            for action in stage.actions:
                if action not in self.actions:
                    raise AgenticConfigError(f"stage {stage.name} references unknown action {action}")
            if stage.next_stage and stage.next_stage != "done" and stage.next_stage not in self.stages:
                raise AgenticConfigError(f"stage {stage.name} references unknown next stage {stage.next_stage}")


def _resolve(root: Path, value: str) -> Path:
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else root / path
```

- [ ] **Step 2: Create section parser**

`contract.py` should parse Markdown chunks from the existing loaded `WorkflowContract.prompt_template`:

```python
"""Agentic workflow policy section parsing."""
from __future__ import annotations

from dataclasses import dataclass
import re


class AgenticPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActorPolicy:
    name: str
    body: str


@dataclass(frozen=True)
class AgenticPolicy:
    orchestrator: str
    actors: dict[str, ActorPolicy]


_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def parse_agentic_policy(markdown_body: str) -> AgenticPolicy:
    sections: list[tuple[str, str]] = []
    matches = list(_HEADING_RE.finditer(markdown_body or ""))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown_body)
        sections.append((match.group(1).strip(), markdown_body[start:end].strip()))

    orchestrator = ""
    actors: dict[str, ActorPolicy] = {}
    for title, body in sections:
        if title == "Orchestrator Policy":
            orchestrator = body
            continue
        if title.startswith("Actor:"):
            name = title.split(":", 1)[1].strip()
            if not name:
                raise AgenticPolicyError("actor policy heading is missing a name")
            actors[name] = ActorPolicy(name=name, body=body)

    if not orchestrator:
        raise AgenticPolicyError("missing # Orchestrator Policy section")
    if not actors:
        raise AgenticPolicyError("missing # Actor: <name> policy sections")
    return AgenticPolicy(orchestrator=orchestrator, actors=actors)
```

- [ ] **Step 3: Commit config and parser**

```bash
git add daedalus/workflows/agentic/config.py daedalus/workflows/agentic/contract.py
git commit -m "feat: parse agentic workflow policy"
```

---

### Task 3: Add State and Prompt Mechanics

**Files:**
- Create: `daedalus/workflows/agentic/state.py`
- Create: `daedalus/workflows/agentic/prompts.py`

- [ ] **Step 1: Create durable state helpers**

`state.py`:

```python
"""Generic durable state for agentic workflows."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass
class WorkflowState:
    workflow: str = "agentic"
    current_stage: str = ""
    status: str = "running"
    attempt: int = 1
    stage_outputs: dict[str, Any] = field(default_factory=dict)
    actor_outputs: dict[str, Any] = field(default_factory=dict)
    action_results: dict[str, Any] = field(default_factory=dict)
    orchestrator_decisions: list[dict[str, Any]] = field(default_factory=list)
    operator_attention: dict[str, Any] | None = None

    @classmethod
    def initial(cls, first_stage: str) -> "WorkflowState":
        return cls(current_stage=first_stage)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorkflowState":
        return cls(**{field_name: raw.get(field_name, getattr(cls(), field_name)) for field_name in cls().__dict__})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_state(path: Path, *, first_stage: str) -> WorkflowState:
    if not path.exists():
        return WorkflowState.initial(first_stage)
    return WorkflowState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_state(path: Path, state: WorkflowState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_audit(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
```

- [ ] **Step 2: Create prompt builders**

`prompts.py`:

```python
"""Prompt assembly for agentic workflows."""
from __future__ import annotations

import json
from typing import Any

from workflows.agentic.config import AgenticConfig
from workflows.agentic.contract import ActorPolicy, AgenticPolicy
from workflows.agentic.state import WorkflowState
from workflows.prompts import render_prompt_template


def build_orchestrator_prompt(
    *,
    config: AgenticConfig,
    policy: AgenticPolicy,
    state: WorkflowState,
    facts: dict[str, Any],
) -> str:
    payload = {
        "config": config.raw,
        "state": state.to_dict(),
        "facts": facts,
        "available_decisions": ["advance", "retry", "run_actor", "run_action", "operator_attention", "complete"],
    }
    return (
        "# Orchestrator Policy\n\n"
        f"{policy.orchestrator}\n\n"
        "# Current Context\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n"
    )


def build_actor_prompt(
    *,
    actor_policy: ActorPolicy,
    variables: dict[str, Any],
) -> str:
    return render_prompt_template(prompt_template=actor_policy.body, variables=variables)
```

- [ ] **Step 3: Commit mechanics**

```bash
git add daedalus/workflows/agentic/state.py daedalus/workflows/agentic/prompts.py
git commit -m "feat: add agentic state and prompts"
```

---

### Task 4: Add Decision, Runtime, Action, and Stage Mechanics

**Files:**
- Create: `daedalus/workflows/agentic/orchestrator.py`
- Create: `daedalus/workflows/agentic/actors.py`
- Create: `daedalus/workflows/agentic/actions.py`
- Create: `daedalus/workflows/agentic/gates.py`
- Create: `daedalus/workflows/agentic/stages.py`

- [ ] **Step 1: Create orchestrator decision validation**

`orchestrator.py`:

```python
"""Orchestrator decision parsing."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import json


class OrchestratorDecisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class OrchestratorDecision:
    decision: str
    stage: str
    target: str | None = None
    reason: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    operator_message: str | None = None

    @classmethod
    def from_output(cls, output: str) -> "OrchestratorDecision":
        try:
            raw = json.loads(output)
        except json.JSONDecodeError as exc:
            raise OrchestratorDecisionError(f"orchestrator returned invalid JSON: {exc}") from exc
        decision = str(raw.get("decision", ""))
        if decision not in {"advance", "retry", "run_actor", "run_action", "operator_attention", "complete"}:
            raise OrchestratorDecisionError(f"unsupported orchestrator decision: {decision}")
        stage = str(raw.get("stage", ""))
        if not stage:
            raise OrchestratorDecisionError("orchestrator decision is missing stage")
        inputs = raw.get("inputs") or {}
        if not isinstance(inputs, dict):
            raise OrchestratorDecisionError("orchestrator decision inputs must be an object")
        return cls(
            decision=decision,
            stage=stage,
            target=raw.get("target"),
            reason=str(raw.get("reason") or ""),
            inputs=inputs,
            operator_message=raw.get("operator_message"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "stage": self.stage,
            "target": self.target,
            "reason": self.reason,
            "inputs": self.inputs,
            "operator_message": self.operator_message,
        }
```

- [ ] **Step 2: Create actor runtime mechanics**

`actors.py`:

```python
"""Actor runtime dispatch for agentic workflows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from workflows.agentic.config import ActorConfig


class ActorRuntime(Protocol):
    def run(self, *, actor: ActorConfig, prompt: str) -> str:
        ...


@dataclass(frozen=True)
class LocalRuntime:
    output: str

    def run(self, *, actor: ActorConfig, prompt: str) -> str:
        return self.output


def build_local_runtime(*, output: str) -> LocalRuntime:
    return LocalRuntime(output=output)
```

- [ ] **Step 3: Create action registry**

`actions.py`:

```python
"""Deterministic actions available to agentic workflows."""
from __future__ import annotations

from dataclasses import dataclass
from subprocess import run
from typing import Any, Callable

from workflows.agentic.config import ActionConfig


@dataclass(frozen=True)
class ActionResult:
    name: str
    ok: bool
    output: dict[str, Any]


ActionHandler = Callable[[ActionConfig, dict[str, Any]], ActionResult]


def run_action(action: ActionConfig, inputs: dict[str, Any]) -> ActionResult:
    handlers: dict[str, ActionHandler] = {
        "noop": _run_noop,
        "command": _run_command,
        "comment": _run_comment,
    }
    handler = handlers.get(action.type)
    if handler is None:
        return ActionResult(name=action.name, ok=False, output={"error": f"unknown action type {action.type}"})
    return handler(action, inputs)


def _run_noop(action: ActionConfig, inputs: dict[str, Any]) -> ActionResult:
    return ActionResult(name=action.name, ok=True, output={"inputs": inputs})


def _run_command(action: ActionConfig, inputs: dict[str, Any]) -> ActionResult:
    command = action.raw.get("command") or inputs.get("command")
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        return ActionResult(name=action.name, ok=False, output={"error": "command action requires a string list"})
    completed = run(command, capture_output=True, text=True, check=False)
    return ActionResult(
        name=action.name,
        ok=completed.returncode == 0,
        output={
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
    )


def _run_comment(action: ActionConfig, inputs: dict[str, Any]) -> ActionResult:
    return ActionResult(name=action.name, ok=True, output={"comment": inputs.get("comment") or action.raw.get("comment")})
```

- [ ] **Step 4: Create gate validation**

`gates.py`:

```python
"""Gate helpers for agentic workflows."""
from __future__ import annotations

from workflows.agentic.config import AgenticConfig, AgenticConfigError


def validate_stage_gates(config: AgenticConfig, stage_name: str) -> None:
    stage = config.stages[stage_name]
    for gate_name in stage.gates:
        gate = config.gates[gate_name]
        if gate.type != "orchestrator-evaluated":
            raise AgenticConfigError(f"unsupported gate type for {gate_name}: {gate.type}")
```

- [ ] **Step 5: Create stage mechanics**

`stages.py`:

```python
"""Mechanical stage operations for agentic workflows."""
from __future__ import annotations

from typing import Any

from workflows.agentic.actions import run_action
from workflows.agentic.config import AgenticConfig
from workflows.agentic.contract import AgenticPolicy
from workflows.agentic.gates import validate_stage_gates
from workflows.agentic.prompts import build_actor_prompt
from workflows.agentic.state import WorkflowState


def actor_variables(*, config: AgenticConfig, state: WorkflowState, inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow": state.to_dict(),
        "config": config.raw,
        **inputs,
    }


def apply_actor_output(*, state: WorkflowState, actor_name: str, output: dict[str, Any]) -> None:
    state.actor_outputs[actor_name] = output


def apply_action_result(*, config: AgenticConfig, state: WorkflowState, action_name: str, inputs: dict[str, Any]) -> None:
    action = config.actions[action_name]
    result = run_action(action, inputs)
    state.action_results[action_name] = {
        "ok": result.ok,
        "output": result.output,
    }


def validate_current_stage(config: AgenticConfig, state: WorkflowState) -> None:
    if state.current_stage not in config.stages:
        raise RuntimeError(f"unknown current stage: {state.current_stage}")
    validate_stage_gates(config, state.current_stage)
```

- [ ] **Step 6: Commit runtime mechanics**

```bash
git add daedalus/workflows/agentic/orchestrator.py daedalus/workflows/agentic/actors.py daedalus/workflows/agentic/actions.py daedalus/workflows/agentic/gates.py daedalus/workflows/agentic/stages.py
git commit -m "feat: add agentic execution mechanics"
```

---

### Task 5: Add CLI Validate, Show, and Tick

**Files:**
- Create: `daedalus/workflows/agentic/cli.py`

- [ ] **Step 1: Implement CLI**

`cli.py`:

```python
"""CLI for the generic agentic workflow."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from workflows.agentic.actors import build_local_runtime
from workflows.agentic.config import AgenticConfig
from workflows.agentic.contract import parse_agentic_policy
from workflows.agentic.orchestrator import OrchestratorDecision
from workflows.agentic.prompts import build_orchestrator_prompt
from workflows.agentic.stages import validate_current_stage
from workflows.agentic.state import append_audit, load_state, save_state
from workflows.contract import load_workflow_contract


def main(workspace: object, argv: list[str]) -> int:
    if not isinstance(workspace, AgenticConfig):
        raise TypeError(f"agentic CLI expected AgenticConfig, got {type(workspace).__name__}")
    parser = argparse.ArgumentParser(prog="agentic")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate")
    subcommands.add_parser("show")
    tick_parser = subcommands.add_parser("tick")
    tick_parser.add_argument("--orchestrator-output", default="")
    args = parser.parse_args(argv)

    if args.command == "validate":
        return _validate(workspace)
    if args.command == "show":
        return _show(workspace)
    if args.command == "tick":
        return _tick(workspace, orchestrator_output=args.orchestrator_output)
    raise RuntimeError(f"unhandled command {args.command}")


def _load_policy(config: AgenticConfig):
    contract = load_workflow_contract(config.workflow_root)
    return parse_agentic_policy(contract.prompt_template)


def _validate(config: AgenticConfig) -> int:
    policy = _load_policy(config)
    missing = [actor for actor in config.actors if actor not in policy.actors and actor != config.orchestrator_actor]
    if missing:
        raise RuntimeError(f"missing actor policy sections: {missing}")
    first_stage = next(iter(config.stages))
    state = load_state(config.storage.state_path, first_stage=first_stage)
    validate_current_stage(config, state)
    print("agentic workflow valid")
    return 0


def _show(config: AgenticConfig) -> int:
    print(json.dumps(config.raw, indent=2, sort_keys=True))
    return 0


def _tick(config: AgenticConfig, *, orchestrator_output: str) -> int:
    policy = _load_policy(config)
    first_stage = next(iter(config.stages))
    state = load_state(config.storage.state_path, first_stage=first_stage)
    validate_current_stage(config, state)
    prompt = build_orchestrator_prompt(config=config, policy=policy, state=state, facts={})
    output = orchestrator_output or build_local_runtime(
        output='{"decision":"complete","stage":"' + state.current_stage + '","target":null,"reason":"local smoke complete","inputs":{},"operator_message":null}'
    ).run(actor=config.actors[config.orchestrator_actor], prompt=prompt)
    decision = OrchestratorDecision.from_output(output)
    state.orchestrator_decisions.append(decision.to_dict())
    if decision.decision == "complete":
        state.status = "complete"
    elif decision.decision == "operator_attention":
        state.status = "operator_attention"
        state.operator_attention = {"message": decision.operator_message, "reason": decision.reason}
    elif decision.decision == "advance":
        target = decision.target or config.stages[state.current_stage].next_stage
        if target == "done":
            state.status = "complete"
        elif target:
            state.current_stage = target
    save_state(config.storage.state_path, state)
    append_audit(config.storage.audit_log_path, {"event": "agentic.tick", "decision": decision.to_dict()})
    print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
    return 0
```

- [ ] **Step 2: Commit CLI**

```bash
git add daedalus/workflows/agentic/cli.py
git commit -m "feat: add agentic workflow cli"
```

---

### Task 6: Update Docs

**Files:**
- Modify: `daedalus/workflows/README.md`
- Modify: `docs/workflows/README.md`

- [ ] **Step 1: Update workflow layout docs**

In `daedalus/workflows/README.md`, add `agentic/` to the layout and include this note:

```markdown
`agentic/` is the clean replacement path for hardcoded workflow policy. It reads `WORKFLOW.md` front matter plus Markdown policy chunks, runs actors/actions mechanically, and stores generic state. `issue_runner/` and `change_delivery/` remain legacy packages until their policies are ported into agentic workflow templates.
```

- [ ] **Step 2: Update public workflow docs**

In `docs/workflows/README.md`, add:

```markdown
## Agentic Workflow

`workflow: agentic` is the policy-driven workflow model. The front matter defines mechanical bindings such as runtimes, actors, stages, gates, actions, and storage. The Markdown body defines orchestrator and actor policies. Python should validate and execute those mechanics, not decide production workflow policy.
```

- [ ] **Step 3: Commit docs**

```bash
git add daedalus/workflows/README.md docs/workflows/README.md
git commit -m "docs: document agentic workflow path"
```

---

### Task 7: Manual Smoke Verification

**Files:**
- No source edits unless smoke checks expose a broken import or invalid command.
- Do not create files under `tests/`.

- [ ] **Step 1: Import the new workflow object**

Run:

```bash
python -c "import sys; sys.path.insert(0, 'daedalus'); from workflows.registry import load_workflow_object; w = load_workflow_object('agentic'); print(w.name)"
```

Expected output:

```text
agentic
```

- [ ] **Step 2: Validate the bundled template through a temporary smoke root**

Run:

```powershell
$tmp = Join-Path $env:TEMP "daedalus-agentic-smoke"
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $tmp | Out-Null
Copy-Item daedalus\workflows\agentic\workflow.template.md (Join-Path $tmp "WORKFLOW.md")
python daedalus\workflows\__main__.py --workflow-root $tmp validate
```

Expected output:

```text
agentic workflow valid
```

- [ ] **Step 3: Run one deterministic tick**

Run:

```powershell
python daedalus\workflows\__main__.py --workflow-root $tmp tick
Get-Content (Join-Path $tmp ".daedalus\agentic-state.json")
```

Expected state contains:

```json
"status": "complete"
```

- [ ] **Step 4: Confirm no test files were created**

Run:

```bash
git status --short
git diff --name-only --diff-filter=A | rg "^tests/" ; if ($LASTEXITCODE -eq 1) { "no new tests" }
```

Expected output includes:

```text
no new tests
```

- [ ] **Step 5: Commit smoke fixes if needed**

Only if Steps 1-4 required source or docs fixes:

```bash
git add daedalus docs
git commit -m "fix: complete agentic workflow first slice"
```

Do not create an empty commit.

---

## Out Of Scope For This Slice

- No deletion of `daedalus/workflows/issue_runner/`.
- No deletion of `daedalus/workflows/change_delivery/`.
- No port of production issue runner policy into an agentic template.
- No port of production change delivery policy into an agentic template.
- No integration actions for tracker updates, PR publish, PR update, or PR merge.
- No new files under `tests/`.
- No broad suite verification.

## Next Slice

After this first slice smokes correctly, port one legacy workflow at a time into `WORKFLOW.md` templates:

1. Port `issue_runner` policy into an agentic template and wire only the mechanical actions it needs.
2. Port `change_delivery` policy into an agentic template and wire tracker/code-host actions.
3. Compare outputs from legacy runs against agentic smoke runs using operator-reviewed traces.
4. Delete legacy folders only after the operator accepts parity.
