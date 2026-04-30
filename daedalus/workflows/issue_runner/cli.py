from __future__ import annotations

import argparse
import json
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate the issue-runner workflow.")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show tracker and last-run status.")
    status.add_argument("--json", action="store_true")

    doctor = sub.add_parser("doctor", help="Validate tracker, workspace, and runtime references.")
    doctor.add_argument("--json", action="store_true")

    tick = sub.add_parser("tick", help="Run one issue-runner dispatch tick.")
    tick.add_argument("--json", action="store_true")

    return parser


def _print_status(status: dict[str, Any]) -> None:
    tracker = status.get("tracker") or {}
    selected = status.get("selectedIssue")
    print(f"health: {status.get('health')}")
    print(f"tracker: {tracker.get('kind')} issues={tracker.get('issueCount')} eligible={tracker.get('eligibleCount')}")
    if selected:
        print(f"selected issue: {selected.get('id')} {selected.get('title')}")
    else:
        print("selected issue: none")
    last_run = status.get("lastRun") or {}
    if last_run:
        print(f"last run: ok={last_run.get('ok')} attempt={last_run.get('attempt')} at={last_run.get('updatedAt')}")


def main(workspace: Any, argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "status":
        payload = workspace.build_status()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            _print_status(payload)
        return 0

    if args.command == "doctor":
        payload = workspace.doctor()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"ok: {payload.get('ok')}")
            for check in payload.get("checks") or []:
                print(f"- {check.get('name')}: {check.get('status')} ({check.get('detail')})")
        return 0 if payload.get("ok") else 1

    if args.command == "tick":
        payload = workspace.tick()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(
                f"ok={payload.get('ok')} issue={((payload.get('selectedIssue') or {}).get('id'))} "
                f"attempt={payload.get('attempt')} output={payload.get('outputPath')}"
            )
        return 0 if payload.get("ok") else 1

    parser.error(f"unknown command: {args.command}")
    return 2

