"""Workflow-plugin dispatcher for Daedalus."""
from __future__ import annotations

from workflows.registry import (
    list_workflows,
    load_workflow,
    load_workflow_object,
    run_cli,
)
from workflows.contract import WorkflowContractError
from workflows.workflow import ModuleWorkflow, Workflow

__all__ = [
    "Workflow",
    "ModuleWorkflow",
    "WorkflowContractError",
    "load_workflow",
    "load_workflow_object",
    "run_cli",
    "list_workflows",
]
