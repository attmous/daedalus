# Repository Guidelines

## Project Structure & Module Organization
`daedalus/` is the shipped plugin payload. Core runtime code lives in files such as `runtime.py`, `tools.py`, and `formatters.py`; workflow-specific logic lives under `daedalus/workflows/code_review/`; reusable project payloads and skills live under `daedalus/projects/` and `daedalus/skills/`. `tests/` mirrors the runtime, workflow, and formatter surfaces with focused pytest files. `docs/` contains architecture notes, operator docs, ADRs, and concept writeups. `scripts/` holds install, migration, and asset-generation helpers. `web/` and `assets/` contain static site and media files.

## Build, Test, and Development Commands
There is no package build step; development is centered on install and test flows.

- `./scripts/install.sh` installs the plugin into the default Hermes location.
- `python3 scripts/install.py --repo-root . --destination /tmp/daedalus` installs to a custom target for local verification.
- `pytest` runs the full suite using `pytest.ini`.
- `pytest tests/test_stall_detection.py -v` runs one focused test file.
- `pytest --cov=daedalus --cov-report=term-missing` checks coverage for runtime or workflow changes.

## Coding Style & Naming Conventions
Use Python with 4-space indentation, snake_case for modules and functions, and PascalCase for classes. Prefer explicit type hints on public logic and keep core code stdlib-first; host dependencies are intentionally minimal. Follow the repo’s fail-soft design: webhooks, observers, and other side effects should catch and report their own failures instead of crashing the main tick loop.

## Testing Guidelines
Add or update tests with every behavior change, especially under `daedalus/workflows/code_review/`. Keep test names descriptive and aligned to the target surface, for example `test_formatters_status.py` or `test_workflows_code_review_reviews.py`. Use focused module tests for local logic and workflow-prefixed tests for lane/state-machine behavior. If you change operator commands, config reload behavior, schema, or status output, update the related docs in `docs/operator/` and `docs/concepts/`.

## Commit & Pull Request Guidelines
Recent history favors short, imperative commits and often uses Conventional Commit prefixes such as `fix(architecture): ...`, `feat(install): ...`, and `docs: ...`. Keep PRs scoped, link the relevant issue, summarize operator or workflow impact, and list the test commands you ran. Include screenshots or GIFs for changes under `web/` or visual assets, and call out any required documentation updates.
