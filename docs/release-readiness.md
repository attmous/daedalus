# Release Readiness

This scorecard tracks what must stay true before Sprints is presented as a
community-ready SDLC workflow engine. It is intentionally mechanical: every item
should be backed by current documentation, compile checks, or operator-visible diagnostics.

## Current Position

- Overall posture: **public beta candidate**, not a strict Symphony
  implementation.
- Reference workflow: `issue-runner`.
- Flagship workflow: `change-delivery`.
- First-class tracker: GitHub.
- First-class code host: GitHub.
- Experimental tracker: Linear.
- Preferred contract: repo-owned `WORKFLOW.md` or `WORKFLOW-<workflow>.md`.

## Symphony Alignment

| Area | Status | Evidence |
|---|---|---|
| Repo-owned workflow contract | Strong | `WORKFLOW*.md` loader, bootstrap, examples, packaged templates |
| Tracker abstraction | Good | Shared GitHub, local JSON, and experimental Linear clients; `change-delivery` separates `tracker` from `code-host` |
| Code-host abstraction | Good | Shared GitHub client owns PR create/list/ready/merge, reactions, and review-thread GraphQL |
| Long-running scheduler | Good | `issue-runner run`, worker supervision, retries, persisted scheduler state |
| Workspace lifecycle | Good | Sanitized issue workspaces, hooks, terminal cleanup, root containment |
| Codex app-server | Good | Managed stdio, external WebSocket, thread resume, token/rate-limit metrics |
| Observability | Good | `/sprints watch`, status, HTTP state, JSONL audit events |
| strict Symphony contract | Partial | Sprints still requires extension fields outside the core Symphony blocks |
| Cross-workflow uniformity | Partial | `issue-runner` is cleaner; `change-delivery` remains intentionally opinionated |

## Verification Alignment

| Area | Status | Evidence |
|---|---|---|
| Repo knowledge as system of record | Strong | Architecture, workflow, operator, security, and conformance docs |
| Public-surface guardrails | Strong | Generic examples, placeholder-only `projects/`, packaging metadata, compile checks |
| Agent-legible workflows | Good | Workflow docs link the default templates and operator paths |
| Operator diagnostics | Good | `/sprints doctor`, `/sprints status`, `/sprints watch`, runtime-matrix checks |

## Gates Before Community Launch

1. Keep `sprints/projects/` placeholder-only in the public repository.
2. Keep README quick start short and route details to `docs/operator/installation.md`.
3. Keep `issue-runner` as the Symphony-shaped reference workflow.
4. Keep GitHub as the documented first-class tracker until live coverage expands.
5. Keep Linear documented as experimental until it has first-class operator docs.
6. Keep workflow examples synchronized with packaged templates.
7. Keep Codex app-server diagnostics operator-visible before calling app-server
   support mature.
8. Keep GitHub automation documented as first-class only while `doctor` and
   runtime-matrix checks expose actionable failures.

## Next Hardening Slice

The highest-leverage next implementation slice is deeper flagship operator evidence:

1. Make `change-delivery` status/reporting explain PR creation and update
   progress without reading raw state.
2. Add bounded operator diagnostics for internal-review loops.
3. Emit release-candidate evidence from existing `/sprints` inspection commands.
