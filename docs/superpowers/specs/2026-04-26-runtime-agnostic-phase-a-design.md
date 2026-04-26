# Runtime-Agnostic Code-Review Workflow — Phase A Design

**Status:** Approved
**Date:** 2026-04-26
**Branch:** `claude/runtime-agnostic-phase-a` (worktree at `.claude/worktrees/runtime-agnostic-phase-a`)
**Baseline:** main `4bdb15b`, 450 tests passing

## Problem

The code-review workflow has model-tied call sites: `actions.py` injects `ensure_acpx_session_fn`, `run_acpx_prompt_fn`, `close_acpx_session_fn` into the action dispatcher; `reviews.py` shells out to `claude` directly for the internal review; `prompts.py` embeds Codex/Claude assumptions in templates. Operators cannot swap Codex for Claude (or for a hermes-agent session) by editing config — they would have to edit Python.

Groundwork already in place: a `Runtime` Protocol with `@register` decorator, `build_runtimes()` factory, and shim functions in `sessions.py` (`ensure_session_via_runtime`, `run_prompt_via_runtime`, `close_session_via_runtime`). `acpx-codex` and `claude-cli` adapters exist. Bundled prompts already live as `.md` files in `workflows/code_review/prompts/`.

Phase A delivers the **foundation** that makes runtime swap operator-controlled: a third runtime kind, a generic dispatcher, config-driven `command:` and `prompt:` overrides, and a workspace-level prompt override directory. Phase B (external reviewer pluggability), Phase C (webhooks), and Phase D (JSON ledger field renames + helper renames) follow as separate PRs.

## Scope

### In scope (this PR)
1. **`hermes-agent` runtime adapter** — third runtime kind, registered as `kind: hermes-agent`, runs prompts by spawning a hermes-agent CLI session and feeding the rendered prompt.
2. **`command:` config field** — optional argv-array override on each runtime profile and on each agent role; placeholders `{model}`, `{prompt_path}`, `{worktree}`, `{session_name}` filled by the dispatcher; agent-role override fully replaces the runtime default.
3. **Generic `dispatch_agent()` function** in new `workflows/code_review/dispatch.py` — single entry point that resolves `(runtime, command, prompt_path, model)` from config, materializes the rendered prompt to a temp file, and invokes the runtime.
4. **Workspace-level prompt overrides** — `dispatch_agent` resolves prompt paths in this order: (1) absolute path from agent's `prompt:` key, (2) `<workspace>/config/prompts/<role>.md`, (3) bundled `workflows/code_review/prompts/<role>.md`. No path ⇒ default by role name.
5. **Schema extension** — add `hermes-agent-runtime` to `runtimes:` `oneOf`; add optional `command:` (array of strings) and `prompt:` (string) to runtime profiles, coder tiers, internal-reviewer, advisory-reviewer.
6. **Tests** — adapter, dispatcher, schema validation, prompt resolution order, command placeholder substitution.
7. **Docs** — `skills/operator/SKILL.md` documents the new agent/runtime/command/prompt config surface.

### Out of scope (deferred)
- **Phase B:** External reviewer pluggability (currently Codex Cloud–tied via `fetch_codex_cloud_review`, `summarize_codex_cloud_review`, etc.).
- **Phase C:** Webhooks — generic event-emitter config for action transitions.
- **Phase D:** Rename pass — `claudeCode` → `internalReview` in JSON ledger (with one-shot migrator), `run_claude_review` action-type literal → `run_internal_review` (transient, no migration), helper renames (`run_acpx_prompt_fn`, `codex_cloud_*`).

## Architecture

### Runtime layering (unchanged, just extended)
```
        ┌─────────────────────────────────────────┐
        │        actions.py / reviews.py          │
        │   (call dispatch_agent, no model lit)   │
        └──────────────────┬──────────────────────┘
                           │
                ┌──────────▼──────────┐
                │  dispatch_agent     │  ← NEW (workflows/code_review/dispatch.py)
                │  - resolve runtime  │
                │  - resolve prompt   │
                │  - render command   │
                │  - run via runtime  │
                └──────────┬──────────┘
                           │
              ┌────────────┼────────────┬────────────┐
              ▼            ▼            ▼            ▼
        ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ AcpxCdx │  │ ClaudeCl │  │ Hermes-  │  │ (future  │
        │ Runtime │  │ iRuntime │  │ Agent RT │  │  kinds)  │
        └─────────┘  └──────────┘  └──────────┘  └──────────┘
```

### Command override semantics
Runtime profile defines a default `command:` argv. Agent role can override with its own `command:`. The override fully replaces the runtime's default — no merging or templating of the runtime command. Runtime adapter validates which placeholders it supports.

```yaml
runtimes:
  codex-acpx:
    kind: acpx-codex
    command: ["acpx", "--model", "{model}", "--cwd", "{worktree}",
              "codex", "prompt", "-s", "{session_name}", "{prompt_path}"]
    session-idle-freshness-seconds: 900
    session-idle-grace-seconds: 1800
    session-nudge-cooldown-seconds: 600

  claude-oneshot:
    kind: claude-cli
    command: ["claude", "--model", "{model}",
              "--permission-mode", "bypassPermissions",
              "--max-turns", "24", "--print", "{prompt_path}"]
    max-turns-per-invocation: 24
    timeout-seconds: 1200

  hermes-coder:
    kind: hermes-agent
    command: ["hermes-agent", "run", "--workspace", "{worktree}",
              "--model", "{model}", "--prompt-file", "{prompt_path}"]

agents:
  coder:
    default:
      runtime: codex-acpx
      model: gpt-5
      # prompt: implied as <workspace>/config/prompts/coder.md
      #         falls back to bundled prompts/coder-dispatch.md
    high:
      runtime: codex-acpx
      model: gpt-5
      command: ["acpx", "--model", "{model}", "--cwd", "{worktree}",
                "codex", "prompt", "-s", "{session_name}",
                "--reasoning", "high", "{prompt_path}"]
  internal-reviewer:
    runtime: claude-oneshot
    model: claude-sonnet-4
    name: claude-sonnet-4-review
    # prompt: implied as <workspace>/config/prompts/internal-reviewer.md
    #         falls back to bundled prompts/internal-review-strict.md
```

### Prompt resolution order
For a given role (e.g. `coder`, `internal-reviewer`):

1. **Explicit `prompt:` in agent role** — absolute path or path relative to workspace config dir.
2. **Workspace override** — `<workspace>/config/prompts/<role>.md` if it exists.
3. **Bundled default** — `workflows/code_review/prompts/<role>.md` (renamed from current files: `coder-dispatch.md` → `coder.md`, `internal-review-strict.md` → `internal-reviewer.md`, `repair-handoff.md` stays).

Prompts remain `.format(**kwargs)` templates; render kwargs continue to come from the call site (issue, worktree, etc.).

### Dispatcher contract
```python
# workflows/code_review/dispatch.py

def dispatch_agent(
    *,
    workspace,
    role: str,                      # "coder", "internal-reviewer", "advisory-reviewer"
    tier: str | None = None,        # for coder: "default", "high", etc.; ignored for flat roles
    rendered_prompt: str,           # already .format()-ed by caller
    session_name: str,
    extra_placeholders: dict[str, str] | None = None,
) -> str:
    """Resolves runtime + command + model from workspace config, materializes
    rendered_prompt to a temp file inside the worktree, runs the command via
    the resolved runtime, returns stdout.

    Raises:
        DispatchConfigError: unknown role/tier, missing runtime, unsupported placeholder.
    """
```

The runtime adapter gains an optional `run_command(*, worktree, command_argv, env=None) -> str` method used by the dispatcher when a `command:` override is present. When no override is present, the runtime's existing `run_prompt(...)` is called (preserves current behavior). All three adapters implement `run_command`.

### Hermes-agent runtime
New `workflows/code_review/runtimes/hermes_agent.py` registered as `kind: hermes-agent`. Behaves like `claude-cli`: no persistent session (`ensure_session`/`close_session` are no-ops, `assess_health` always healthy). Default command shape:

```
hermes-agent run --workspace {worktree} --model {model} --prompt-file {prompt_path}
```

The exact CLI surface is operator-configurable via `command:` — Phase A doesn't pin a specific hermes-agent CLI shape; the default just illustrates what an operator would write.

## Data flow (one tick example: coder dispatch)

1. `actions.py` decides `dispatch_codex_turn`.
2. Caller renders the prompt via `prompts.render_implementation_dispatch_prompt(...)` (returns string).
3. Caller calls `dispatch_agent(workspace=ws, role="coder", tier="default", rendered_prompt=prompt, session_name="lane-issue-42")`.
4. Dispatcher reads `agents.coder.default` from config → `(runtime="codex-acpx", model="gpt-5", command=<runtime-default>, prompt=<implicit>)`.
5. Dispatcher writes `rendered_prompt` to `<worktree>/.daedalus/dispatch/coder-default-<sha>.txt`, then resolves the prompt-template path (workspace override → bundled default) — note the rendered prompt and the prompt template path are **two different files**: the template was already `.format()`-ed in step 2; the path passed via `{prompt_path}` is the rendered file.
6. Dispatcher fills placeholders in command argv (`{model}`, `{prompt_path}`, `{worktree}`, `{session_name}`) and invokes `runtime.run_command(worktree=..., command_argv=...)`.
7. Returns stdout.

For `internal-reviewer` (one-shot, no session): same flow, runtime is `claude-cli`, `session_name` is generated synthetically and ignored by the adapter.

## Migration path for live `yoyopod` workspace

1. Existing `workflow.yaml` continues to validate (new fields are optional).
2. No `command:` overrides present ⇒ runtime adapters fall through to their built-in `run_prompt` paths (current behavior preserved exactly).
3. No workspace `config/prompts/` directory present ⇒ bundled prompts used.
4. Bundled prompt rename: `coder-dispatch.md` → `coder.md`, `internal-review-strict.md` → `internal-reviewer.md` (both files moved + renamed in this PR; `prompts.py` updates the `_load_template` calls).
5. Action-type literal `run_claude_review` stays unchanged (Phase D problem).
6. JSON ledger fields (`claudeCode`, `lastClaudeVerdict`) stay unchanged (Phase D problem).

Net effect on the live workspace: no behavior change unless the operator opts in by adding `command:` overrides or `<workspace>/config/prompts/*.md` files.

## Schema changes

```yaml
# Inside runtimes: oneOf (existing)
oneOf:
  - $ref: "#/definitions/acpx-codex-runtime"
  - $ref: "#/definitions/claude-cli-runtime"
  - $ref: "#/definitions/hermes-agent-runtime"   # NEW

# All three runtime definitions gain (optional):
command:
  type: array
  items: {type: string}
  minItems: 1

# coder-tier definition gains (optional):
command:
  type: array
  items: {type: string}
  minItems: 1
prompt:
  type: string  # path; absolute or relative to workspace config dir

# internal-reviewer / advisory-reviewer gain the same (optional) command + prompt fields.

# NEW definition:
hermes-agent-runtime:
  type: object
  required: [kind]
  properties:
    kind: {const: hermes-agent}
    command:
      type: array
      items: {type: string}
      minItems: 1
```

## Tests

New file `tests/test_runtime_agnostic_phase_a.py`:
- `test_hermes_agent_runtime_registered` — `_RUNTIME_KINDS["hermes-agent"]` resolves to `HermesAgentRuntime`.
- `test_hermes_agent_run_command` — adapter invokes `run` with correct argv.
- `test_dispatch_agent_resolves_workspace_prompt_override` — `<workspace>/config/prompts/coder.md` shadows bundled default.
- `test_dispatch_agent_resolves_explicit_prompt_path` — agent's `prompt:` key wins over workspace override.
- `test_dispatch_agent_falls_back_to_bundled` — no override anywhere ⇒ bundled `prompts/coder.md`.
- `test_dispatch_agent_substitutes_placeholders` — command argv has `{model}`, `{prompt_path}`, `{worktree}`, `{session_name}` filled.
- `test_dispatch_agent_unknown_role_raises` — `DispatchConfigError`.
- `test_dispatch_agent_uses_runtime_default_when_no_override` — agent without `command:` falls through to runtime profile's `command:`; if neither has one, runtime's built-in `run_prompt` is called.

New file `tests/test_runtime_agnostic_schema.py`:
- `test_schema_accepts_hermes_agent_runtime`
- `test_schema_accepts_command_override_on_runtime`
- `test_schema_accepts_command_override_on_coder_tier`
- `test_schema_accepts_prompt_override_on_internal_reviewer`
- `test_schema_rejects_empty_command_array`
- `test_existing_yoyopod_workflow_yaml_still_validates` — load the live `~/.hermes/workflows/yoyopod/config/workflow.yaml` and assert it validates (behavior preservation).

Existing 450 tests stay green. Target: 450 + ~14 new = ~464 passing.

## Open questions

None — all locked in based on user choices:
- Prompts: file refs at conventional paths (`prompts/<role>.md`), with workspace override.
- `command:` override: full replacement, runtime-supplied placeholders.
- Phase A scope: foundation only; no persisted-state changes; rename pass deferred to Phase D.
