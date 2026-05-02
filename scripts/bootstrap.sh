#!/usr/bin/env bash
# Curl-pipe installer for Sprints.
# Clones the repo to a cache directory and runs scripts/install.sh.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/attmous/sprints/main/scripts/bootstrap.sh | bash
#
# Pass install flags through:
#   curl -fsSL .../bootstrap.sh | bash -s -- --hermes-home /path
#
# Environment overrides:
#   SPRINTS_HOME       clone destination (default: $HOME/.local/share/sprints)
#   SPRINTS_REPO_URL   repo URL (default: upstream)

set -euo pipefail

REPO_URL="${SPRINTS_REPO_URL:-https://github.com/attmous/sprints.git}"
DEST="${SPRINTS_HOME:-$HOME/.local/share/sprints}"

if ! command -v git >/dev/null 2>&1; then
  echo "error: git is required but not installed" >&2
  exit 1
fi

if [ -d "$DEST/.git" ]; then
  echo "Updating Sprints at $DEST..."
  git -C "$DEST" pull --ff-only --quiet
else
  echo "Cloning Sprints to $DEST..."
  mkdir -p "$(dirname "$DEST")"
  git clone --depth 1 --quiet "$REPO_URL" "$DEST"
fi

echo "Running installer..."
exec "$DEST/scripts/install.sh" "$@"
