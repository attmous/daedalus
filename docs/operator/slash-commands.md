# Sprints slash command catalog

Quick reference for the two slash commands the plugin registers in Hermes:
`/sprints` (engine + service control) and `/workflow` (per-workflow operations).

For the operator playbook ("when something looks wrong, do X"), see
`docs/operator/cheat-sheet.md`. This file is a flat catalog: every command,
grouped by purpose, with a one-line description.

Workflow-specific commands are grouped by workflow below. Do not assume every
workflow exposes the richer `change-delivery` command surface.

## `/sprints` — engine + service control

### Inspection (read-only)

| Command | What it does |
|---|---|
| `/sprints status` | Runtime row + lane count + paths (DB, event log) |
| `/sprints doctor` | Full health check across all subsystems |
| `/sprints validate` | Validate `WORKFLOW.md`, schema, service mode, and workflow preflight |
| `/sprints runtime-matrix` | Show workflow role-to-runtime bindings and optional tiny runtime-stage smoke results |
| `/sprints events` | Query the durable engine event ledger |
| `/sprints events stats` | Count durable events by type/severity and show retention posture |
| `/sprints events prune` | Apply explicit or `WORKFLOW.md` event retention immediately |
| `/sprints runs` | Inspect durable engine run history |
| `/sprints shadow-report` | `change-delivery` shadow-mode action proposal vs active/runtime state |
| `/sprints active-gate-status` | Active-execution gate state and blockers |

### Inspection output format

All inspection commands default to a structured human-readable panel.
Pass `--format json` (or the legacy `--json` alias) for machine-readable JSON.
ANSI color is auto-detected via `sys.stdout.isatty()` and respects the
`NO_COLOR` environment variable.

#### Example: `/sprints status`

```
Sprints runtime — <owner>-<repo>-<workflow-type>
  state    running (active mode)
  owner    sprints-active-<owner>-<repo>-<workflow-type>
  schema   v3
  paths
    db          ~/.hermes/workflows/<owner>-<repo>-<workflow-type>/runtime/state/sprints/sprints.db
    events      ~/.hermes/workflows/<owner>-<repo>-<workflow-type>/runtime/memory/sprints-events.jsonl
  heartbeat
    last        22:43:01 UTC (17s ago)
  lanes
    total       14
```

#### Example: `/sprints active-gate-status`

```
Active execution gate
  ✓ ownership posture  primary_owner = sprints
  ✓ active execution   enabled
  ✓ runtime mode       running in active
  ✓ previous scheduler retired (engine_owner = hermes)

→ gate is open: actions can dispatch
```

When blocked:

```
Active execution gate
  ✓ ownership posture  primary_owner = sprints
  ✗ active execution   DISABLED  set via /sprints set-active-execution --enabled true
  ✓ runtime mode       running in active
  ✓ previous scheduler retired (engine_owner = hermes)

→ gate is BLOCKED: no actions will dispatch
```

#### Example: `/sprints doctor`

```
Sprints doctor
  ✓ overall  PASS
  checks
    ✓ missing_lease       Runtime lease present
    ✓ shadow_compatible   Shadow decision matches active policy
    ✓ active_execution_failures  No active execution failures
```

#### Example: `/sprints shadow-report`

```
Sprints shadow-report
  runtime
    state           running (active mode)
  owner           sprints-active-<owner>-<repo>-<workflow-type>
    heartbeat       22:43:01 UTC (17s ago)
    lease expires   22:44:00 UTC (in 42s)
  ownership
    primary owner       sprints
    sprints primary    yes
    ✓ active execution  yes
    ✓ gate allowed      yes
  service
    mode        active
    installed   yes
    enabled     yes
    active      yes
  active lane
    issue     #329
    lane id   lane-329
    state     under_review / pass / pending
  next action
    workflow      publish_pr   head-clean
    sprints      publish_pr   head-clean
    ✓ compatible  yes
```

#### Example: `/sprints service-status`

```
Sprints service
  service  sprints-active@<owner>-<repo>-<workflow-type>.service
  mode     active
  install state
    ✓ installed   yes
    ✓ enabled     yes
    ✓ active      yes
  runtime
    pid   12345
  paths
    unit  ~/.config/systemd/user/sprints-active@.service
```

### Operational control

| Command | What it does |
|---|---|
| `/sprints start` | Bootstrap runtime row + emit start event |
| `/sprints run-active` | Supervised active service loop (use systemd; not this directly) |
| `/sprints run-shadow` | Shadow loop (use systemd; not this directly) |
| `/sprints iterate-active` | One tick of the active loop |
| `/sprints iterate-shadow` | One tick of the shadow loop |
| `/sprints set-active-execution` | Enable/disable active dispatch |

### State management

| Command | What it does |
|---|---|
| `/sprints init` | Init/migrate the runtime DB (idempotent) |
| `/sprints bootstrap` | Infer repo root + GitHub slug from the current checkout, create a workflow state root, write the repo-owned workflow contract, and persist a repo-local workflow pointer |
| `/sprints scaffold-workflow` | Create a new workflow root named `<owner>-<repo>-<workflow-type>` and write the repo-owned workflow contract |
| `/sprints ingest-live` | Pull workflow CLI status into the ledger |
| `/sprints heartbeat` | Refresh the runtime lease |
| `/sprints request-active-actions` | Inspect what *would* be dispatched on the next tick |
| `/sprints execute-action` | Manually execute a queued action |
| `/sprints analyze-failure` | Run failure analyst on a specific failure id |

### Systemd supervision

| Command | What it does |
|---|---|
| `/sprints service-up` | Validate `WORKFLOW.md`, then install, enable, and start the user unit |
| `/sprints service-install` | Install the user unit only |
| `/sprints service-uninstall` | Stop + remove the user unit |
| `/sprints service-start` | Start `sprints-active@<workspace>.service` |
| `/sprints service-stop` | Stop the service |
| `/sprints service-restart` | Restart the service |
| `/sprints service-enable` | Enable on boot |
| `/sprints service-disable` | Disable on boot |
| `/sprints service-status` | systemd status snapshot |
| `/sprints service-logs` | Last N journal entries |
| `/sprints codex-app-server install` | Write the shared Codex app-server user unit |
| `/sprints codex-app-server up` | Install, enable, and start the shared Codex app-server |
| `/sprints codex-app-server status` | Show unit status plus `GET /readyz` readiness |
| `/sprints codex-app-server doctor` | Diagnose managed/external listener health, auth posture, and Codex thread mappings |
| `/sprints codex-app-server restart` | Restart the Codex app-server unit |
| `/sprints codex-app-server logs` | Last N Codex app-server journal entries |
| `/sprints codex-app-server down` | Stop and disable Codex app-server |

### Observability

| Command | What it does |
|---|---|
| `/sprints watch` | Live operator TUI (lanes + alerts + recent events) |
| `/sprints watch --once` | Render one frame and exit (works in pipes) |

## `/workflow` — per-workflow operations

|| Command | What it does |
|---|---|---|
|| `/workflow` | List installed workflows |
|| `/workflow <name>` | Show that workflow's `--help` |
|| `/workflow <name> <cmd> [args]` | Route to that workflow's CLI |

### `change-delivery` workflow shortcuts (the common ones)

This is the opinionated managed SDLC workflow.

|| Command | What it does |
|---|---|---|
|| `/workflow change-delivery status` | Lane state + `nextAction` |
|| `/workflow change-delivery tick` | One workflow tick |
|| `/workflow change-delivery show-active-lane` | Current active GitHub issue |
|| `/workflow change-delivery show-lane-state` | `.lane-state.json` contents |
|| `/workflow change-delivery show-lane-memo` | `.lane-memo.md` contents |
|| `/workflow change-delivery dispatch-implementation-turn` | Force an implementation actor turn |
|| `/workflow change-delivery dispatch-internal-review` | Force an internal review |
|| `/workflow change-delivery publish-ready-pr` | Force PR publish |
|| `/workflow change-delivery merge-and-promote` | Force merge + promote next lane |
|| `/workflow change-delivery reconcile` | Repair stale ledger state |
|| `/workflow change-delivery pause` | Disable lane processing |
|| `/workflow change-delivery resume` | Re-enable |
|| `/workflow change-delivery serve` | Run the optional localhost HTTP status server |

### `issue-runner` workflow shortcuts

This is the bundled generic tracker-driven workflow.

|| Command | What it does |
|---|---|---|
|| `/workflow issue-runner status` | Selected issue + last run summary |
|| `/workflow issue-runner doctor` | Validate tracker, workspace, and runtime references |
|| `/workflow issue-runner tick` | Run one synchronous issue-runner dispatch tick |
|| `/workflow issue-runner run` | Run the supervised long-lived issue-runner polling loop |
|| `/workflow issue-runner serve` | Run the optional localhost HTTP status server |

## Most useful day-to-day, in order

1. `/sprints watch` — live overview of every active lane in one frame
2. `/sprints doctor` — overall health
3. `/workflow <name> status` — workflow-specific current state
4. `/sprints service-logs` — last 50 journal entries from the active service
5. `/workflow change-delivery tick` or `/workflow issue-runner tick` — manually fire a tick when impatient

## Notes

- All `/sprints` subcommands accept `--workflow-root <path>` (default: detected from the cwd or `SPRINTS_WORKFLOW_ROOT` env var).
- A few commands accept `--json` (`status`, `ingest-live`, `request-active-actions`); per-workflow CLI commands also accept `--json` where the underlying workflow supports it.
- The output format is currently terse `key=value` strings. Improving readability is tracked in the Sprints repo's issue tracker.
