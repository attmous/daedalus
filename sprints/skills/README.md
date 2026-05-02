# Sprints Skills

Bundled Sprints skills are project-agnostic mechanics for actor work. Workflow
policy stays in `WORKFLOW.md`; skills only describe repeatable execution steps.

## Bundled Skills

```text
skills/
|-- pull/      # sync branch with origin/main
|-- debug/     # diagnose blocked or failing actor work
|-- commit/    # commit verified lane changes
|-- push/      # push branch and create/update PR
`-- land/      # operator/reviewer PR landing support
```

The default `change-delivery` implementer uses `pull`, `debug`, `commit`, and
`push`. The `push` skill owns pull request creation or update.
