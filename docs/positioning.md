# Sprints vs. Hermes Agent vs. Hermes Kanban

Sprints, Hermes Agent, and Hermes Kanban all coordinate agentic work, but they
sit at different layers. Keeping those layers separate avoids duplicate
schedulers and makes Sprints useful without taking over every Hermes feature.

```mermaid
flowchart TD
    Tracker[Trackers and boards<br/>GitHub Issues, local-json, future Linear, future Hermes Kanban]
    Sprints[Sprints engine<br/>ticks, leases, SQLite state, workflow reconciliation]
    Workflow[Workflow packages<br/>issue-runner, change-delivery, future workflows]
    Runtime[Runtimes<br/>Hermes Agent, Codex app-server, CLI agents, custom commands]
    CodeHost[Code hosts<br/>branches, PRs, checks, reviews, merge]

    Tracker --> Sprints
    Sprints --> Workflow
    Workflow --> Runtime
    Workflow --> CodeHost
```

## Short Version

| System | Primary job | Best fit |
|---|---|---|
| Hermes Agent | Run an agent with tools, memory, skills, models, messaging, and runtime surfaces. | The execution platform Sprints can call into. |
| Hermes Kanban | Durable multi-agent task board with task states, dependencies, run history, and worker claims. | Optional local-first tracker or planning board. |
| Sprints | Durable SDLC workflow engine that turns issues into governed workflow runs. | Software delivery automation: issue selection, runtime dispatch, PR/review/merge gates, recovery. |

## Where They Overlap

Hermes Kanban and Sprints are both engine-like. Both use durable state, track
work attempts, support claim/retry/recovery semantics, and expose operator
surfaces. That overlap is why Kanban should not become Sprints' internal
scheduler. Running one scheduler inside another would create unclear ownership
for claims, retries, blocked work, and terminal states.

## What Each Does Not Own

| System | Intentional limitation |
|---|---|
| Hermes Agent | It runs agents and exposes tools, but it should not own Sprints workflow policy, SDLC gates, tracker reconciliation, or PR/merge semantics. |
| Hermes Kanban | It coordinates generic tasks, but it should not own Sprints lane leases, runtime role dispatch, GitHub PR lifecycle, CI/review gates, or workflow recovery policy. |
| Sprints | It automates SDLC workflows, but it should not become a general personal/team Kanban board, messaging gateway, model provider router, or universal Hermes task UI. |

## Why Sprints Is Not Duplication

Hermes Kanban can say: "task X is ready and assigned to profile Y." Sprints
adds the SDLC-specific layer: "issue X becomes a lane, role A uses runtime B,
thread IDs are persisted, tracker feedback is posted, a PR is created or
updated, review gates are enforced, CI and merge state are reconciled, and
stalled work is recovered."

That SDLC layer is the reason Sprints remains necessary even when Hermes
Kanban exists.

## Integration Stance

Hermes Agent should remain a first-class runtime surface. Sprints should call
it through runtime adapters such as `hermes-agent` and, later, optional
`hermes-acp`.

Hermes Kanban should be integrated later as a tracker adapter, not as a
replacement engine:

```yaml
tracker:
  kind: hermes-kanban
  tenant: my-project
  assignee: sprints
```

In that shape, Sprints reads candidate tasks from Kanban and writes comments or
state updates back, while Sprints still owns workflow execution, leases,
runtime dispatch, gates, reconciliation, and code-host side effects.

## Current Priority

Keep GitHub first-class for `change-delivery` because GitHub is where issues,
branches, PRs, reviews, checks, and merge state already live. Add Hermes Kanban
later for local demos, personal task queues, non-GitHub work, and fleet-style
operator planning.

References:

- [Hermes Agent ACP integration](https://hermes-agent.nousresearch.com/docs/user-guide/features/acp)
- [Hermes Kanban overview](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban)
- [Hermes Kanban tutorial](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban-tutorial)
