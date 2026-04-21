# hermes-relay

hermes-relay is a Hermes plugin that provides a relay runtime, alert logic, and an operator control surface for workflow-oriented orchestration.

Contents:
- `__init__.py` — plugin registration
- `schemas.py` — CLI/slash parser wiring
- `tools.py` — operator surface and systemd helpers
- `runtime.py` — canonical relay runtime implementation
- `alerts.py` — outage alert decision logic
- `plugin.yaml` — plugin manifest
- `skills/operator/SKILL.md` — operator workflow notes
- `scripts/install.py` — Python installer for the plugin payload
- `scripts/install.sh` — shell wrapper around the installer

## Intended placement

This repository is the source of truth for the plugin payload. Install it into a Hermes plugins directory, for example:

```text
~/.hermes/plugins/hermes-relay/
```

Or inside a project-local plugin tree:

```text
<project-root>/
  .hermes/
    plugins/
      hermes-relay/
```

## Installation

Default Hermes installation target:

```bash
./scripts/install.sh
```

Install into a non-default Hermes home:

```bash
./scripts/install.sh --hermes-home /path/to/hermes-home
```

Install into an explicit destination directory:

```bash
./scripts/install.sh --destination /path/to/plugins/hermes-relay
```

The installer copies the plugin payload only:
- `__init__.py`
- `alerts.py`
- `plugin.yaml`
- `runtime.py`
- `schemas.py`
- `tools.py`
- `skills/`

## Usage

Inside a Hermes session with project plugins enabled:

```bash
export HERMES_ENABLE_PROJECT_PLUGINS=true
cd <project-root>
hermes
```

Then use:

```text
/relay status
/relay shadow-report
/relay doctor
/relay cutover-status
/relay iterate-active --json
```

For direct runtime invocation from the plugin path:

```bash
python3 ~/.hermes/plugins/hermes-relay/runtime.py status --workflow-root <workflow-root> --json
python3 ~/.hermes/plugins/hermes-relay/runtime.py run-active --workflow-root <workflow-root> --project-key <project-key> --instance-id relay-active-service-1 --interval-seconds 30 --json
python3 ~/.hermes/plugins/hermes-relay/alerts.py --workflow-root <workflow-root> --json
```

## Notes

- The runtime is workflow-aware and expects a compatible workflow root.
- `tools.py` can install a systemd user service that points directly at the plugin runtime path.
- This repository is the plugin source of truth; downstream wrappers or mirrors can be removed as consumers migrate.
