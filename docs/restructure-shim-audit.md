# Restructure Shim Audit

Status: current after package flattening.

Sprints now keeps only the public package surfaces that are still used by the
plugin runtime and direct CLI execution.

## Retained Public Packages

- `engine`
- `workflows`
- `runtimes`
- `trackers`

## Removed Compatibility Shims

- `sprints.operator`
- `sprints.integrations`
- `sprints.code_hosts`
- `sprints.trackers.feedback`
- `sprints.trackers.local_json`
- legacy workflow packages: `issue_runner` and `change_delivery`

New code should import the concrete current modules directly. Do not recreate
shim packages unless an active external caller requires one.
