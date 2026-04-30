---
workflow: issue-runner
schema-version: 1

instance:
  name: your-org-your-repo-issue-runner
  engine-owner: hermes

repository:
  local-path: /home/you/src/acme-repo
  github-slug: your-org/your-repo

tracker:
  kind: local-json
  path: config/issues.json
  active-states:
    - todo
    - in-progress
  terminal-states:
    - done
    - canceled

polling:
  interval-seconds: 30

workspace:
  root: workspace/issues

hooks:
  timeout-seconds: 60

runtimes:
  default:
    kind: claude-cli
    max-turns-per-invocation: 24
    timeout-seconds: 1200

agent:
  name: Issue_Runner_Agent
  model: claude-sonnet-4-6
  runtime: default
  max-concurrent-issues: 1

retry:
  continuation-delay-seconds: 1
  initial-backoff-seconds: 10
  max-backoff-seconds: 300
  max-attempts: 5

storage:
  status: memory/workflow-status.json
  health: memory/workflow-health.json
  audit-log: memory/workflow-audit.jsonl
---

# Workflow Policy

Daedalus runs the `issue-runner` workflow against the tracker configured above.

Shared rules:

- Work only on the selected issue and its stated scope.
- Prefer explicit handoffs over silent assumptions.
- Record blockers clearly when you cannot continue safely.
- Keep outputs grounded in the current issue state and repository checkout.

