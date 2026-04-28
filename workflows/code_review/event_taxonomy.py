"""Symphony §10.4-aligned event taxonomy.

Single source of truth for canonical event names. Writers (in runtime.py)
emit only constants from this module; readers (status.py, observability.py,
watch.py, server views) wrap event-type reads in `canonicalize()` so old
log files keep working during the one-release alias window.

Design:
- Symphony's bare session/turn lifecycle names (session_started, …)
- Daedalus-native orchestration events under `daedalus.*` prefix
- EVENT_ALIASES maps legacy Daedalus event names to their new canonical
  equivalents. Readers consult this map; writers do not.
"""
from __future__ import annotations


# ---- Symphony §10.4 session/turn-level events ----
SESSION_STARTED       = "session_started"
TURN_COMPLETED        = "turn_completed"
TURN_FAILED           = "turn_failed"
TURN_CANCELLED        = "turn_cancelled"
TURN_INPUT_REQUIRED   = "turn_input_required"
NOTIFICATION          = "notification"
UNSUPPORTED_TOOL_CALL = "unsupported_tool_call"
MALFORMED             = "malformed"
STARTUP_FAILED        = "startup_failed"

# ---- Daedalus-native events (no Symphony equivalent) ----
DAEDALUS_LANE_CLAIMED         = "daedalus.lane_claimed"
DAEDALUS_LANE_RELEASED        = "daedalus.lane_released"
DAEDALUS_REPAIR_HANDOFF       = "daedalus.repair_handoff_dispatched"
DAEDALUS_REVIEW_LANDED        = "daedalus.review_landed"
DAEDALUS_VERDICT_PUBLISHED    = "daedalus.verdict_published"
DAEDALUS_CONFIG_RELOADED      = "daedalus.config_reloaded"
DAEDALUS_CONFIG_RELOAD_FAILED = "daedalus.config_reload_failed"
DAEDALUS_DISPATCH_SKIPPED     = "daedalus.dispatch_skipped"
DAEDALUS_STALL_DETECTED       = "daedalus.stall_detected"
DAEDALUS_STALL_TERMINATED     = "daedalus.stall_terminated"
DAEDALUS_REFRESH_REQUESTED    = "daedalus.refresh_requested"


# ---- One-release alias window: legacy -> canonical ----
EVENT_ALIASES: dict[str, str] = {
    "claude_review_started":     SESSION_STARTED,
    "claude_review_completed":   TURN_COMPLETED,
    "claude_review_failed":      TURN_FAILED,
    "codex_handoff_dispatched":  DAEDALUS_REPAIR_HANDOFF,
    "internal_review_started":   SESSION_STARTED,
    "internal_review_completed": TURN_COMPLETED,
    "internal_review_failed":    TURN_FAILED,
    "external_review_landed":    DAEDALUS_REVIEW_LANDED,
    "verdict_published":         DAEDALUS_VERDICT_PUBLISHED,
    "lane_claimed":              DAEDALUS_LANE_CLAIMED,
    "lane_released":             DAEDALUS_LANE_RELEASED,
}


def canonicalize(event_type: str) -> str:
    """Resolve a possibly-legacy event-type string to its canonical form.

    Idempotent for already-canonical names. Unknown names pass through
    unchanged so readers don't lose information."""
    return EVENT_ALIASES.get(event_type, event_type)
