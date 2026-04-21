#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PLUGIN_NAME = "hermes-relay"
PAYLOAD_ITEMS = [
    "__init__.py",
    "alerts.py",
    "plugin.yaml",
    "runtime.py",
    "schemas.py",
    "tools.py",
    "skills",
]


def resolve_destination(*, hermes_home: Path | None = None, destination: Path | None = None) -> Path:
    if destination is not None:
        return destination.expanduser().resolve()
    hermes_root = (hermes_home or Path.home() / ".hermes").expanduser().resolve()
    return hermes_root / "plugins" / PLUGIN_NAME


def install_plugin(*, repo_root: Path, hermes_home: Path | None = None, destination: Path | None = None) -> Path:
    repo_root = repo_root.expanduser().resolve()
    target = resolve_destination(hermes_home=hermes_home, destination=destination)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    for item in PAYLOAD_ITEMS:
        source = repo_root / item
        if not source.exists():
            raise FileNotFoundError(f"missing payload item: {source}")
        dest = target / item
        if source.is_dir():
            shutil.copytree(source, dest)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the hermes-relay plugin into a Hermes plugins directory.")
    parser.add_argument("--hermes-home", help="Hermes home directory. Default: ~/.hermes")
    parser.add_argument("--destination", help="Explicit plugin destination directory. Overrides --hermes-home.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]), help="Source repository root. Default: this repository root.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    target = install_plugin(
        repo_root=Path(args.repo_root),
        hermes_home=Path(args.hermes_home) if args.hermes_home else None,
        destination=Path(args.destination) if args.destination else None,
    )
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
