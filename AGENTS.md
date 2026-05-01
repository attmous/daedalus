# Repository Guidelines

## Project Structure & Module Organization

`daedalus/` is the main Python package for the Hermes Agent plugin: CLI surfaces, runtime adapters, trackers, workflows, formatters, skills, and migrations. Bundled workflow implementations live in `daedalus/workflows/change_delivery/` and `daedalus/workflows/issue_runner/`. Root-level `runtime.py`, `schemas.py`, `workflows/`, `runtimes/`, and `trackers/` are compatibility entry points. Tests live in `tests/`; docs in `docs/`; static web assets in `web/`; packaging metadata in `pyproject.toml`, `MANIFEST.in`, and `plugin.yaml`.

## Build, Test, and Development Commands

- `python3 -m pip install -r requirements-dev.txt`: install runtime and test dependencies.
- `python3 -m pip install .`: install the package locally with the `hermes_agent.plugins` entry point.
- `./scripts/install.sh`: install into the local Hermes plugin environment.
- `pytest`: run the full CI test suite.
- `pytest tests/test_stall_detection.py -v`: run one focused test file.
- `pytest --cov=daedalus --cov-report=term-missing`: run coverage locally.
- `hermes daedalus validate`: validate a generated workflow contract when Hermes is available.

## Coding Style & Naming Conventions

Use Python 3.10+ syntax, 4-space indentation, and PEP 8-compatible formatting. New Python modules should use type hints and `from __future__ import annotations`. Modules and functions use `snake_case`, classes use `PascalCase`, constants use `UPPER_SNAKE_CASE`, and workflow files use descriptive lowercase names. Avoid new core dependencies beyond stdlib, SQLite, and existing project dependencies. Keep operator JSON machine-readable and formatter output human-readable.

## Testing Guidelines

Pytest is the test framework; `pytest.ini` sets `tests/` as the test path and adds `daedalus` to `pythonpath`. Name tests `test_<module>.py` or `test_workflows_<workflow>_<topic>.py`. Add focused tests when changing workflow state, schemas, runtime adapters, CLI behavior, packaging, or docs drift. Keep public onboarding and packaging checks green: `tests/test_public_onboarding_smoke.py`, `tests/test_official_plugin_layout.py`, and `tests/test_pip_plugin_packaging.py`.

## Commit & Pull Request Guidelines

Git history uses short, imperative subjects such as `Add runtime preset configuration command` or `Document Daedalus positioning`; keep commits focused. Pull requests should describe behavior changes, link issues, call out docs or schema updates, and include test commands run. Include screenshots or terminal output when changing operator watch/status rendering or web assets.

## Security & Configuration Tips

Do not commit generated workflow roots, local state databases, JSONL event logs, credentials, or `.hermes/` pointers from target repositories. Keep `daedalus/projects/**` placeholder-only in the public package. When changing files loaded via `Path(__file__).parent` such as prompts, skills, workflow templates, or `plugin.yaml`, update packaging metadata and rerun the packaging tests.
