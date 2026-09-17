#!/usr/bin/env bash
# Cursor Cloud install hook: provision PT runtime and test dependencies.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if command -v uv >/dev/null 2>&1; then
  UV_BIN="$(command -v uv)"
else
  UV_BOOTSTRAP_DIR="${TMPDIR:-/tmp}/perpetua-tools-uv"
  python3 -m venv "$UV_BOOTSTRAP_DIR"
  "$UV_BOOTSTRAP_DIR/bin/python" -m pip install --quiet --upgrade pip uv
  UV_BIN="$UV_BOOTSTRAP_DIR/bin/uv"
fi

"$UV_BIN" sync --extra dev --frozen
.venv/bin/python -m pytest --version
bash scripts/cursor/cloud-bootstrap.sh
