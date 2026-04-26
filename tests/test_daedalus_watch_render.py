"""Frame rendering: aggregator output → rich-renderable frame string.

We render to a string (capture mode) and snapshot-test the output structure.
"""
import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _module():
    return load_module("daedalus_watch_test", "watch.py")


def test_render_frame_with_no_active_lanes():
    watch = _module()
    out = watch.render_frame_to_string({
        "active_lanes": [],
        "alert_state": {},
        "recent_events": [],
    })
    assert "Daedalus active lanes" in out
    assert "(no active lanes)" in out


def test_render_frame_with_one_lane():
    watch = _module()
    out = watch.render_frame_to_string({
        "active_lanes": [
            {"lane_id": "329", "state": "under_review", "github_issue_number": 329}
        ],
        "alert_state": {},
        "recent_events": [
            {"at": "2026-04-26T22:30:34Z", "source": "workflow", "event": "dispatch_implementation_turn", "detail": "committed"},
        ],
    })
    assert "329" in out
    assert "under_review" in out
    assert "dispatch_implementation_turn" in out


def test_render_frame_includes_alert_banner_when_alert_active():
    watch = _module()
    out = watch.render_frame_to_string({
        "active_lanes": [],
        "alert_state": {"active": True, "fingerprint": "abc", "message": "stale heartbeat"},
        "recent_events": [],
    })
    assert "Active alerts" in out or "alert" in out.lower()


def test_render_frame_handles_stale_source():
    """Source-level [stale] markers when an aggregator returned an error sentinel."""
    watch = _module()
    out = watch.render_frame_to_string({
        "active_lanes": [{"_stale": True}],
        "alert_state": {"_stale": True},
        "recent_events": [],
    })
    # No crash; "[stale]" appears somewhere
    assert "stale" in out.lower()
