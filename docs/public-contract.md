# Public contract

This document defines the stability boundary for the first public Daedalus release.

## Stable surfaces

These are the surfaces we should treat as `v1` public contract:

- `WORKFLOW.md` at the workflow root for workflow instance configuration
- legacy `config/workflow.yaml` loading for existing instances
- `hermes plugins install attmous/daedalus --enable`
- the `hermes_agent.plugins` entry point name `daedalus`
- `hermes daedalus bootstrap`
- `hermes daedalus scaffold-workflow`
- `hermes daedalus service-up`
- `hermes daedalus init`
- `hermes daedalus service-*`
- `/daedalus ...` operator commands
- `/workflow <name> ...` workflow commands
- the workflow root naming convention: `~/.hermes/workflows/<owner>-<repo>-<workflow-type>`
- the repo-local workflow pointer written by `bootstrap`: `./.hermes/daedalus/workflow-root`

Changes to those surfaces should be documented, tested, and treated as compatibility-sensitive.

## Internal implementation

These are not public compatibility promises yet:

- SQLite schema details in `runtime/state/daedalus/daedalus.db`
- event payload internals beyond documented operator output
- archived design/spec material under `docs/superpowers/`
- source-repo playground material under `daedalus/projects/**` (not shipped in
  the public plugin payload)
- experimental skills and local migration helpers

We can refactor those freely as long as the stable surfaces above keep working.

## Bundled workflows

- `workflow: change-delivery`
  This is the supported managed workflow behind the public `bootstrap` and `service-up` path.
- `workflow: issue-runner`
  This is bundled as a generic reference workflow and loads through `/workflow ...` plus explicit `scaffold-workflow`, but it is not yet part of the managed `bootstrap` / `service-up` contract.

## Contract preference

The preferred and scaffolded public path is `WORKFLOW.md`.

`config/workflow.yaml` remains loadable for legacy workflow roots, but new
docs, templates, and operators should treat it as migration input rather than
the primary contract.
