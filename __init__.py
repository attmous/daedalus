"""Repo-root Hermes plugin entrypoint.

Hermes' official Git install path expects ``plugin.yaml`` and ``__init__.py``
at the repository root. The real implementation lives under ``./sprints/``.
This wrapper keeps the repo installable via ``hermes plugins install`` without
moving the engine package again.
"""

from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent
_INNER_SPRINTS_DIR = _PLUGIN_ROOT / "sprints"
if "__path__" in globals() and _INNER_SPRINTS_DIR.exists():
    _inner_dir_str = str(_INNER_SPRINTS_DIR)
    if _inner_dir_str in __path__:
        __path__.remove(_inner_dir_str)
    __path__.insert(0, _inner_dir_str)

try:
    from .sprints import register as _register
except ImportError:
    from sprints import register as _register


def register(ctx):
    return _register(ctx)
