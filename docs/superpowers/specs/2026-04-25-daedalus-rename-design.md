# Daedalus Rename — Design Spec

**Date:** 2026-04-25
**Status:** Approved (auto mode, single-sweep)
**Predecessors:**
- `docs/adr/ADR-0002-workflows-contract.md` — workflow-plugin contract foundation
- `docs/superpowers/specs/2026-04-24-workflows-contract-and-code-review-design.md` — most recent rename-adjacent work

---

## 1. Goal

Rebrand the project from `hermes-relay` to **Daedalus** in a single clean sweep. No legacy compatibility shims, no dual names, no deprecation cycle. Every surface that today says `relay`, `hermes-relay`, `Hermes Relay`, `HERMES_RELAY_*`, `relay.db`, `relay-events.jsonl`, `yoyopod-relay-*.service`, etc. moves to its Daedalus equivalent in one branch.

**Why now:** the workflows-contract migration just landed (30 commits on `main`, 244 tests green, live YoyoPod workspace idle on `no-active-lane`). Maximum leverage for a rename — the codebase is fresh, no external consumers depend on the old identity, and we can do the live cutover in a 30-second maintenance window.

**Brand decision:** Daedalus. The master craftsman of Greek myth — patron of artisans, builder of complex devices. Stays in the Hermes mythological lineage but more precisely describes what the project is: an engine that orchestrates other agents through structured workflows.

---

## 2. Non-goals

- Visual identity redesign (SVG icon shapes/colors stay; only the file names and any embedded text strings change)
- Brand voice / marketing copy rewrite (mechanical find-replace handles most prose; a real "Daedalus voice" pass is deferred)
- Backward compatibility for any old name (env vars, file paths, table names, command names — all hard cut)
- New workflow types (testing, security_review) — those come later
- Multi-workspace operation beyond what the systemd template unit redesign enables (no second workspace gets onboarded as part of this rename)

---

## 3. Architectural decisions

The decisions below were converged in chat before writing this spec. Listed for the record.

1. **Hard cut, no shims.** Every renamed surface goes from old → new in one branch. No fallback env vars, no DB filename aliasing, no `/relay` slash command alias. The runtime DB and event log get a one-shot file-rename migrator (item 6 below) but nothing else carries over.

2. **Slash command split.**
   - `/daedalus <cmd>` — engine commands (status, doctor, cutover-switch, service-*, etc.) — direct rename of today's `/relay`.
   - `/workflow <name> <cmd> [args]` — per-workflow operations, routes through `workflows.run_cli(workflow_root, [cmd, *args], require_workflow=name)`.

3. **Systemd template units.** Two template units (`daedalus-active@.service`, `daedalus-shadow@.service`), instance name = workspace key under `~/.hermes/workflows/`. Replaces today's hardcoded `yoyopod-relay-{shadow,active}.service`. Enables multiple workspaces to coexist on one host without name collisions.

4. **Plugin install dir renames.** `~/.hermes/plugins/hermes-relay/` → `~/.hermes/plugins/daedalus/`. The live YoyoPod symlink (per `tests/test_install.py:46-73`) gets retargeted as part of the cutover.

5. **Runtime DB and event log get a one-shot migrator.** Plain Python rename of old paths to new paths at startup, idempotent, safe if files don't exist. Systemd unit migration is a separate explicit operator command (different privilege model).

6. **Filesystem layout.**
   - `state/relay/relay.db` → `state/daedalus/daedalus.db`
   - `memory/relay-events.jsonl` → `memory/daedalus-events.jsonl`
   - `memory/hermes-relay-alert-state.json` → `memory/daedalus-alert-state.json`

7. **Internal Python identifier rename is in scope.** Class names, function names, SQL table names, event type strings, error message literals — every `relay` identifier becomes `daedalus`. (See full inventory in Section 4.)

---

## 4. Surface area inventory

This is the full list of renames. Anything in this list is in scope; anything not in it is either out of scope (Section 2) or not yet identified and should be flagged when found.

### 4.1 Repository + plugin identity

| Surface | Old | New |
|---|---|---|
| GitHub repo | `hermes-relay` | `daedalus` |
| `plugin.yaml` `name:` | `hermes-relay` | `daedalus` |
| `plugin.yaml` `description:` | "Hermes Relay operator control surface…" | "Daedalus workflow engine and operator control surface." |
| `scripts/install.py::PLUGIN_NAME` | `"hermes-relay"` | `"daedalus"` |
| Plugin install dir | `~/.hermes/plugins/hermes-relay/` | `~/.hermes/plugins/daedalus/` |

### 4.2 Slash commands + CLI registration

In `__init__.py::register(ctx)`:

| Surface | Old | New |
|---|---|---|
| `ctx.register_command(...)` name | `"relay"` | `"daedalus"` |
| `ctx.register_command(...)` description | "Operate the Hermes Relay runtime…" | "Operate the Daedalus workflow engine from the current Hermes session." |
| `ctx.register_cli_command(...)` name | `"relay"` | `"daedalus"` |
| `ctx.register_cli_command(...)` help/description | "Hermes Relay project control surface" | "Daedalus workflow engine control surface" |
| `ctx.register_skill(...)` description | "Operate the Hermes Relay plugin." | "Operate the Daedalus engine." |
| **NEW** `ctx.register_command("workflow", …)` | (does not exist) | new top-level command routing to `workflows.run_cli` |

**`/workflow` semantics:**

- `/workflow` (no args) → prints `available workflows: code-review` (enumerated by scanning `workflows/` package for valid contract modules)
- `/workflow code-review` → equivalent to `python3 -m workflows --workflow-root <root> code-review --help`
- `/workflow code-review status --json` → equivalent to `python3 -m workflows --workflow-root <root> code-review status --json`

### 4.3 Python module + identifier renames

In `__init__.py`, `schemas.py`, `tools.py`, `runtime.py`, `alerts.py`, `scripts/install.py`, `workflows/code_review/workspace.py`, and every test file under `tests/`:

| Old identifier | New identifier |
|---|---|
| `_load_local_module` key prefix `hermes_relay_` | `daedalus_` |
| `RelayCommandError` | `DaedalusCommandError` |
| `_load_relay_module(...)` | `_load_daedalus_module(...)` |
| `init_relay_db(...)` | `init_daedalus_db(...)` |
| `append_relay_event(...)` | `append_daedalus_event(...)` |
| `RELAY_SCHEMA_VERSION` | `DAEDALUS_SCHEMA_VERSION` |
| Variable `relay = _load_relay_module(...)` | `daedalus = _load_daedalus_module(...)` |
| Argparse subparser dest `args.relay_command` | `args.daedalus_command` |

**Test file `_load_local_module` keys** (e.g. `"hermes_relay_workflows_code_review_workspace_test"`) are also renamed to `daedalus_*`. There are ~50 such keys across the test suite — they're cosmetic (importlib spec name strings) but get cleaned for consistency.

### 4.4 SQL schema

In `runtime.py`, the SQLite schema:

| Old | New |
|---|---|
| Table name `relay_runtime` | `daedalus_runtime` |
| `runtime_id='relay'` row literal | `runtime_id='daedalus'` |
| `instance_id` defaults `"relay-shadow-v1"` etc. (init values) | `"daedalus-shadow-v1"` etc. |

The `relay_runtime` table is the heartbeat / mode / ownership row. It contains operational state (current mode, latest_heartbeat_at, schema_version, etc.) but no irreplaceable data — the row is recreated by `init_daedalus_db` on first call. The migrator (Section 6) handles the rename by:

1. Renaming the file `relay.db` → `daedalus.db`
2. On open, `init_daedalus_db` notices the table is named `relay_runtime` and runs `ALTER TABLE relay_runtime RENAME TO daedalus_runtime`
3. Updates the `runtime_id` value from `'relay'` → `'daedalus'` in the existing row

**Other tables** (`leases`, `lanes`, `lane_actors`, `lane_actions`, `lane_reviews`, `failures`, `state_projections`, `ownership_controls`) keep their names — they describe the workflow domain, not the engine identity.

### 4.5 Event log identifiers

In `runtime.py`, the JSONL event log has two engine-level event types:

| Old | New |
|---|---|
| `event_type: "relay_runtime_started"` | `daedalus_runtime_started` |
| `event_type: "relay_runtime_heartbeat"` | `daedalus_runtime_heartbeat` |
| `event_id` prefix `evt:relay_runtime_*` | `evt:daedalus_runtime_*` |
| `dedupe_key` prefix `relay_runtime_*` | `daedalus_runtime_*` |

Lane/action/review event types are unchanged (they describe the workflow domain, not the engine).

The historical event log on the live YoyoPod machine contains old `relay_runtime_*` events — these stay untouched in the migrated `daedalus-events.jsonl` file. The event log is append-only; old entries record what actually happened at the time and shouldn't be rewritten. New entries written after migration use the new event type strings.

### 4.6 Filesystem paths

In `workflows/code_review/paths.py` (the single source of truth):

| Old | New |
|---|---|
| `state/relay/relay.db` | `state/daedalus/daedalus.db` |
| `memory/relay-events.jsonl` | `memory/daedalus-events.jsonl` |
| `memory/hermes-relay-alert-state.json` | `memory/daedalus-alert-state.json` |
| `.hermes/plugins/hermes-relay/runtime.py` | `.hermes/plugins/daedalus/runtime.py` |
| `.hermes/plugins/hermes-relay/workflows/__main__.py` | `.hermes/plugins/daedalus/workflows/__main__.py` |

Same string also appears in `tools.py:179, 193`, `workflows/code_review/workspace.py:244`, and several test files — all updated mechanically.

### 4.7 Environment variables

Every env var rename is a hard cut.

| Old | New |
|---|---|
| `HERMES_RELAY_WORKFLOW_ROOT` | `DAEDALUS_WORKFLOW_ROOT` |
| `YOYOPOD_RELAY_WORKFLOW_ROOT` | (deleted — was a project-prefixed alias of the above; merged into `DAEDALUS_WORKFLOW_ROOT`) |
| `RELAY_SYSTEMD_USER_DIR` (test override) | `DAEDALUS_SYSTEMD_USER_DIR` |

The separate `YOYOPOD_WORKFLOW_ROOT` env var (no `_RELAY_` infix) stays — it's project-scoped, not engine-scoped.

After this rename, the env var resolution order is:

1. Explicit `--workflow-root` flag
2. `DAEDALUS_WORKFLOW_ROOT`
3. `YOYOPOD_WORKFLOW_ROOT` (project default)
4. Computed fallback (three parents up from the plugin dir)

### 4.8 Systemd units

In `tools.py`, the `SERVICE_PROFILES` dict and surrounding constants:

| Old | New |
|---|---|
| `DEFAULT_SHADOW_SERVICE_INSTANCE_ID = "relay-shadow-service-1"` | (removed — instance ID derived from systemd `%i`) |
| `DEFAULT_SHADOW_SERVICE_NAME = "yoyopod-relay-shadow.service"` | `DAEDALUS_SHADOW_TEMPLATE_UNIT = "daedalus-shadow@.service"` |
| `DEFAULT_ACTIVE_SERVICE_NAME = "yoyopod-relay-active.service"` | `DAEDALUS_ACTIVE_TEMPLATE_UNIT = "daedalus-active@.service"` |
| Service profile `service_name` fields (literal strings) | template unit names with `%i` instance |

**Template unit content** (both modes follow this shape):

```ini
# ~/.config/systemd/user/daedalus-active@.service
[Unit]
Description=Daedalus active orchestrator (workspace=%i)

[Service]
Type=simple
WorkingDirectory=%h/.hermes/workflows/%i
ExecStart=/usr/bin/python3 %h/.hermes/plugins/daedalus/runtime.py run-active \
  --workflow-root %h/.hermes/workflows/%i \
  --project-key %i \
  --instance-id daedalus-active-%i \
  --interval-seconds 30
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=default.target
```

Workspace key (instance name) is the directory name under `~/.hermes/workflows/`. For the live system: `daedalus-active@yoyopod.service`, `daedalus-shadow@yoyopod.service`. The `--instance-id` derives from `%i` so the DB row identifying the running orchestrator is per-workspace per-mode (`daedalus-active-yoyopod`, `daedalus-shadow-yoyopod`).

**`SERVICE_PROFILES` shape after rename:** still keyed by `"shadow"` / `"active"`, each entry now stores the template unit filename and a callable that builds the instance-qualified name from a workspace key.

### 4.9 String literals in user-facing prose

In `tools.py`:

| Old | New |
|---|---|
| `f"relay error: {exc}"` (and adjacent error formatters) | `f"daedalus error: {exc}"` |
| `"Relay runtime is not initialized; run \`relay start\` first"` | `"Daedalus runtime is not initialized; run \`daedalus start\` first"` |
| `f"unknown relay command: {args.relay_command}"` | `f"unknown daedalus command: {args.daedalus_command}"` |
| Argparse help texts mentioning "Relay" / "YoYoPod Relay" | renamed to "Daedalus" |

In `alerts.py:39`:

| Old | New |
|---|---|
| `if result.startswith("relay error:")` | `if result.startswith("daedalus error:")` |

This literal-checking is brittle but lives in one place and gets renamed atomically with `tools.py`.

### 4.10 Skill directory renames

| Old | New |
|---|---|
| `skills/hermes-relay-architecture/` | `skills/daedalus-architecture/` |
| `skills/hermes-relay-hardening-slices/` | `skills/daedalus-hardening-slices/` |
| `skills/hermes-relay-model1-project-layout/` | `skills/daedalus-model1-project-layout/` |
| `skills/hermes-relay-retire-watchdog-and-migrate-control-schema/` | `skills/daedalus-retire-watchdog-and-migrate-control-schema/` |
| `skills/yoyopod-relay-alerts-monitoring/` | `skills/yoyopod-daedalus-alerts-monitoring/` |
| `skills/yoyopod-relay-outage-alerts/` | `skills/yoyopod-daedalus-outage-alerts/` |

Skills with `yoyopod-` prefix that aren't relay-specific (e.g. `yoyopod-closeout-notifier`, `yoyopod-lane-automation`, `yoyopod-workflow-watchdog-tick`) keep their names.

`tests/test_plugin_skills.py:31-35` enumerates expected skill directory names and gets updated.

### 4.11 Asset renames

| Old | New |
|---|---|
| `assets/hermes-relay-icon.svg` | `assets/daedalus-icon.svg` |
| `assets/hermes-relay-wordmark.svg` | `assets/daedalus-wordmark.svg` |

Internal SVG XML may contain text like `Hermes Relay` (in the wordmark) — those text nodes are updated to `Daedalus`. Visual elements (shapes, colors, layout) untouched.

### 4.12 Documentation prose

Mechanical find-replace across all `*.md` files in `README.md`, `docs/`, `skills/*/SKILL.md`:

| Pattern | Replacement |
|---|---|
| `hermes-relay` (lowercase, hyphenated) | `daedalus` |
| `Hermes Relay` (title case) | `Daedalus` |
| `HERMES_RELAY_` (env var prefix) | `DAEDALUS_` |
| `relay.db` | `daedalus.db` |
| `relay-events.jsonl` | `daedalus-events.jsonl` |
| `hermes-relay-alert-state` | `daedalus-alert-state` |
| `yoyopod-relay-active.service` / `…-shadow.service` | `daedalus-active@yoyopod.service` / `daedalus-shadow@yoyopod.service` |
| `/relay status` (and other `/relay <cmd>`) | `/daedalus status` |
| `state/relay/` (path fragment) | `state/daedalus/` |

After the mechanical pass, a manual scan looks for prose that talks about "the relay" as a noun and replaces with "Daedalus" or "the runtime"/"the engine" depending on context. Any historical references in commit messages or ADRs stay (they record what was true at the time).

---

## 5. New components

### 5.1 `migration.py` (new module)

A new top-level module in the plugin that owns startup-time file migrations. Single public function:

```python
def migrate_filesystem_state(workflow_root: Path) -> list[str]:
    """Idempotent rename of relay-era paths to daedalus paths.

    Returns a list of human-readable rename descriptions for logging.
    Safe to call when no migration is needed (returns empty list).
    """
```

Behavior:

1. If `state/daedalus/daedalus.db` does not exist AND `state/relay/relay.db` does → mkdir new parent, rename `relay.db` → `daedalus.db`. Also rename SQLite sidecars if present: `relay.db-wal` → `daedalus.db-wal`, `relay.db-shm` → `daedalus.db-shm` (SQLite WAL mode requires the sidecar filenames to match the DB filename — if we leave them mismatched SQLite either ignores the WAL or creates fresh empty sidecars and loses uncommitted data).
2. If `memory/daedalus-events.jsonl` does not exist AND `memory/relay-events.jsonl` does → rename, log
3. If `memory/daedalus-alert-state.json` does not exist AND `memory/hermes-relay-alert-state.json` does → rename, log
4. If old `state/relay/` dir is empty after the move → remove

**Trigger:** called at the top of `init_daedalus_db` in `runtime.py`, before any DB connection opens. Also exposed as `daedalus migrate-filesystem` (a new subcommand of the registered Daedalus CLI, defined in `schemas.py::setup_cli` and dispatched in `tools.py`) for explicit operator invocation.

**Order of operations inside `init_daedalus_db`:**

```python
def init_daedalus_db(db_path: Path, project_key: str) -> sqlite3.Connection:
    # 1. Filesystem-level migration (renames files if old paths exist)
    migrate_filesystem_state(workflow_root_for(db_path))

    # 2. Open SQLite connection on the now-canonical path
    conn = sqlite3.connect(str(db_path))

    # 3. SQL-level identity migration (idempotent)
    _migrate_schema_identity(conn)
    #    - if table 'relay_runtime' exists: ALTER TABLE relay_runtime RENAME TO daedalus_runtime
    #    - if row with runtime_id='relay' exists: UPDATE daedalus_runtime SET runtime_id='daedalus' WHERE runtime_id='relay'
    #    - both no-ops on a fresh DB or already-migrated DB

    # 4. Normal init: CREATE TABLE IF NOT EXISTS daedalus_runtime (...) and the rest.
    #    No-ops on an already-migrated DB; full init on a fresh one.
    _create_schema(conn)
    _ensure_runtime_row(conn, project_key)
    return conn
```

The SQL identity migration runs **before** the `CREATE TABLE IF NOT EXISTS daedalus_runtime` so the rename happens cleanly without creating a duplicate table.

### 5.2 `daedalus migrate-systemd` (new operator command)

A separate explicit subcommand for the systemd-side cutover. Defined in `schemas.py::setup_cli` and dispatched in `tools.py`:

1. Detects old units (`yoyopod-relay-active.service`, `yoyopod-relay-shadow.service`) under `~/.config/systemd/user/`. **Tolerant of missing units** — if the shadow unit was never installed (the live system runs in active mode only), skip it without error.
2. For each detected old unit: stop (ignore "Unit not loaded" errors), disable (ignore "Failed to disable" errors), then `unlink` the unit file.
3. Installs the new template units (`daedalus-active@.service`, `daedalus-shadow@.service`) per Section 4.8.
4. If an old unit was active before this command ran, enable + start the corresponding new instance (`daedalus-active@<workspace>.service`) where `<workspace>` is derived from the workflow_root the command was invoked under.
5. Reports the transition: `removed: [...]`, `installed: [...]`, `started: [...]`.
6. Runs `systemctl --user daemon-reload` after unit file changes.

Idempotent: if old units don't exist, just installs (or refreshes) the new template. Safe to re-run.

This is **not** auto-triggered. The operator runs it explicitly during the cutover sequence (Section 6).

### 5.3 `/workflow` slash command handler (new)

Lives in `tools.py` (or a new sibling like `workflow_command.py` if it grows). Wired in `__init__.py::register(ctx)`:

```python
ctx.register_command(
    "workflow",
    execute_workflow_command,
    description="Run a workflow's CLI (e.g. /workflow code-review status).",
)
```

`execute_workflow_command(args, *, workflow_root)` parses `<name> <subcmd> [args]`, calls `workflows.run_cli(workflow_root, [subcmd, *args], require_workflow=name)`, and formats the result. With no args, lists available workflows by introspecting `workflows/`. With name only, calls the workflow's `--help`.

---

## 6. Cutover sequence (live YoyoPod)

This is the only operationally interesting part. Order matters.

**Pre-flight (on YoyoPod machine):**

1. Confirm idle: `python3 -m workflows --workflow-root ~/.hermes/workflows/yoyopod status` → no active lane
2. Note current systemd state: `systemctl --user is-active yoyopod-relay-active.service`

**Cutover:**

1. `systemctl --user stop yoyopod-relay-active.service`
2. `cd ~/WS/hermes-relay && git pull` (fetch the rename branch)
3. `./scripts/install.sh` — installs the new payload to `~/.hermes/plugins/daedalus/`
   - Note: install script removes the old `~/.hermes/plugins/hermes-relay/` symlink and creates a new `~/.hermes/plugins/daedalus/` symlink
4. `daedalus migrate-systemd --workflow-root ~/.hermes/workflows/yoyopod` — removes old units, installs new template units, starts `daedalus-active@yoyopod.service`
5. First run of `runtime.py` triggers the filesystem migrator (Section 5.1) automatically — DB + event log + alert state files renamed
6. Verify: `/daedalus status` → healthy, `/daedalus doctor` → no issues
7. Optional smoke: `/workflow code-review status` → idle, no active lane

**Total downtime:** ~30 seconds (steps 1 → 6). Workspace is idle so no work is in flight.

**Rollback:** branch is on `main` only after the cutover succeeds. If anything fails, `git revert` the rename branch, reinstall the old payload, manually rename `daedalus.db` back to `relay.db` (and event log + alert state), reinstall the old systemd units. Documented in the operator skill.

---

## 7. Test strategy

**Existing tests:** every reference to old names gets updated mechanically. Test count stays the same (244 + new tests below).

**New focused tests (in scope of this rename):**

| Test file | Coverage |
|---|---|
| `tests/test_daedalus_migration.py` | Filesystem migrator: 4 cases — clean (no old, no new), partial (only old), full-old (all three old files exist), full-new (already migrated, no-op) |
| `tests/test_daedalus_db_schema_migration.py` | SQL rename within `init_daedalus_db`: 3 cases — fresh DB, DB with `relay_runtime` table needing rename, DB with already-renamed `daedalus_runtime` table |
| `tests/test_systemd_template_units.py` | Template unit file generation: instance name expansion, mode-specific differences, idempotent reinstall |
| `tests/test_workflow_slash_command.py` | `/workflow` dispatch: bare invocation lists workflows, name-only invokes help, full invocation routes to `run_cli` with `require_workflow` |

**Smoke test on live YoyoPod:** post-cutover, verify the four critical paths (status, doctor, tick, service status) all return healthy. Manual, not automated.

**Verification gate before cutover:** all 244 + new tests must pass on the rename branch.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Live DB has data the migrator misses | Migrator only renames files. SQL schema migration runs inside `init_daedalus_db` with `ALTER TABLE` — atomic, well-supported by SQLite. The runtime DB has no irreplaceable data; worst case we delete and re-init. |
| Systemd cutover loses a running service | Pre-flight confirms idle. The migrator stops old, installs new, starts new — bounded downtime. If start fails, old unit files are gone but the new template units are valid systemd, so `systemctl start` works as soon as the issue is fixed. |
| Plugin directory rename leaves broken symlinks | The install script handles symlink removal + recreation in one step (per `tests/test_install.py:46-73`). Tested. |
| Skill directory rename breaks references in skill loader | Only `operator` is registered programmatically (`__init__.py:39`); other skills are filesystem-discovered. Renaming directories is sufficient. `tests/test_plugin_skills.py` enumerates expected names and catches mismatches. |
| External cron jobs reference old systemd unit names | The two archived job definitions in `~/.hermes/workflows/yoyopod/archive/openclaw-cron-jobs.json` reference relay-era state file paths but are disabled (`"enabled": false`). They get a comment update during migration but stay disabled. |
| Hidden references missed by find-replace | The implementation plan has an explicit "grep audit" task at the end that searches for residual `relay`, `Relay`, `RELAY`, `hermes-relay` strings across the entire tree and flags anything found. |

---

## 9. Migration of pre-existing test failure

`tests/test_runtime_tools_alerts.py` is currently failing (pre-existed before workflows-contract migration; flagged in earlier work). It hardcodes `state/relay/relay.db` paths in test fixtures (lines 46, 451). This rename has to update those references whether or not the underlying test failure is resolved.

If the underlying failure is unrelated to identifiers (which is likely — it's a logic-layer test), updating the path strings is a clean independent change. If the failure becomes resolvable as a side effect of the rename (unlikely), bonus points.

The plan task that touches this file does the path-string update only. The unrelated failure stays out of scope of the rename.

---

## 10. Out-of-scope items captured for later

These would be reasonable follow-ups but aren't part of this rename:

- Real "Daedalus voice" rewrite of marketing prose in `README.md` and the operator skill (currently mechanical find-replace produces serviceable but not branded copy)
- New SVG visual identity for the rebrand (current SVGs keep their visuals; only filename + embedded text changes)
- A second workspace test of the multi-workspace systemd template (we install the template; we don't onboard a second workspace as part of this rename)
- Renaming the `model1` and `legacy_workflow_module` artifacts that still reference older code paths (out of scope — they're separate concerns from the rebrand)

---

## 11. Definition of done

The rename is complete when:

1. All renames in Section 4 are implemented
2. New components in Section 5 exist and are tested
3. `pytest` runs green for 244 + new tests (excluding the pre-existing `test_runtime_tools_alerts.py` failure)
4. The cutover sequence (Section 6) has run successfully on the live YoyoPod machine
5. `/daedalus status` and `/workflow code-review status` both return healthy on the live workspace
6. A grep audit finds no residual `hermes-relay`, `Hermes Relay`, `HERMES_RELAY`, `_load_relay_module`, `RelayCommandError`, `relay.db`, `relay-events.jsonl`, `yoyopod-relay-*.service` strings in the codebase. Allowlisted historical artifacts:
   - `docs/adr/ADR-0001-*.md`, `docs/adr/ADR-0002-*.md` — historical decisions, immutable
   - `docs/superpowers/specs/2026-04-24-*.md`, `docs/superpowers/plans/2026-04-24-*.md` — prior workflows-contract spec/plan, immutable
   - This spec itself (`docs/superpowers/specs/2026-04-25-daedalus-rename-design.md`) — references old names by necessity in the rename mapping
   - The new ADR-0003 — references old names for context
   - Git commit messages — immutable
   - Event log entries written pre-cutover — immutable history
7. ADR-0003 captures the rebrand decision (similar shape to ADR-0002)
8. `plugin.yaml` version bumps from `0.2.0` → `0.3.0` to reflect the breaking identity change
