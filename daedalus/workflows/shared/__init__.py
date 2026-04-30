"""Shared workflow infrastructure reused across bundled workflows.

This package holds the generic parts of the workflow system that are not
specific to one lifecycle policy:

- workflow-root resolution and plugin path helpers
- immutable config snapshots and hot-reload primitives
- runtime adapter registry
- stall detection helpers

Policy-heavy code stays in individual workflow packages such as
``workflows.change_delivery`` and ``workflows.issue_runner``.
"""

