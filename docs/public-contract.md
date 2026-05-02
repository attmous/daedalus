# Public contract

This document defines the stability boundary for the first public Sprints release.

## Stable surfaces

These are the surfaces we should treat as `v1` public contract:

- repo-owned workflow contracts:
  - `WORKFLOW.md` when a repo carries one workflow
  - `WORKFLOW-<workflow>.md` when a repo carries multiple workflows
  - bootstrap promotion from `WORKFLOW.md` to named contracts must not
    overwrite existing named contracts
- `hermes plugins install attmous/sprints --enable`
- the `hermes_agent.plugins` entry point name `sprints`
- `hermes sprints bootstrap`
- `hermes sprints scaffold-workflow`
- `hermes sprints service-up`
- `hermes sprints init`
- `hermes sprints service-*`
- `/sprints ...` operator commands
- `/workflow <name> ...` workflow commands
- the workflow root naming convention: `~/.hermes/workflows/<owner>-<repo>-<workflow-type>`
- the repo-local workflow pointer written by `bootstrap`: `./.hermes/sprints/workflow-root`
- the workflow-root contract pointer written under runtime state

Changes to those surfaces should be documented, tested, and treated as compatibility-sensitive.

## Internal implementation

These are not public compatibility promises yet:

- SQLite schema details in `runtime/state/sprints/sprints.db`
- event payload internals beyond documented operator output
- placeholder-only source tree under `sprints/projects/**` (not shipped in the
  public plugin payload)
- experimental skills and local migration helpers

We can refactor those freely as long as the stable surfaces above keep working.

## Restructure guardrails

The implementation source of truth is `sprints/`. Repo-root compatibility
packages are not part of the public contract; direct imports should use the
installed plugin layout or the `sprints.<package>` package path.

## Bundled workflows

- `workflow: change-delivery`
  This is the supported managed workflow behind the public `bootstrap` and `service-up` path.
- `workflow: issue-runner`
  This is bundled as the generic tracker-driven workflow. It supports the same repo-owned `WORKFLOW*.md`, `bootstrap` / `scaffold-workflow`, and `service-up` path, but its managed service mode is `active` only.

## Contract preference

The preferred and scaffolded public path is a repo-owned `WORKFLOW*.md`.

`config/workflow.yaml` is not a supported public workflow contract. Use
repo-owned `WORKFLOW.md` or `WORKFLOW-<workflow>.md`.
