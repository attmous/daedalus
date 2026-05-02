"""Repo-root wrapper for the official Hermes plugin layout."""

try:
    from .sprints.sprints_cli import *  # noqa: F401,F403
    from .sprints.sprints_cli import execute_raw_args as _execute_raw_args
except ImportError:
    from sprints.sprints_cli import *  # noqa: F401,F403
    from sprints.sprints_cli import execute_raw_args as _execute_raw_args


if __name__ == "__main__":
    import sys

    result = _execute_raw_args(" ".join(sys.argv[1:]))
    print(result)
    sys.exit(0 if not result.startswith("sprints error:") else 1)
