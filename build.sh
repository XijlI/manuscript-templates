#!/usr/bin/env bash
# POSIX convenience wrapper — all logic lives in build.py so that Windows /
# VS Code can run the same driver without a bash on PATH.
set -euo pipefail
cd "$(dirname "$0")"
exec python build.py "$@"
