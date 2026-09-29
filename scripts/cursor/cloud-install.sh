#!/usr/bin/env bash
# Cursor Cloud install hook: provision PT runtime and test dependencies.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

UV_BIN=""
if command -v uv >/dev/null 2>&1; then
  UV_BIN="$(command -v uv)"
elif [[ -x "${HOME}/.local/bin/uv" ]]; then
  UV_BIN="${HOME}/.local/bin/uv"
fi

if [[ -z "$UV_BIN" ]]; then
  # Default Cursor Cloud images ship python3 without ensurepip / python3-venv.
  # Bootstrap uv via the standalone installer (no venv required).
  UV_INSTALL_DIR="${HOME}/.local/bin"
  mkdir -p "$UV_INSTALL_DIR"
  curl -fsSL https://astral.sh/uv/install.sh | env \
    UV_INSTALL_DIR="$UV_INSTALL_DIR" \
    UV_NO_MODIFY_PATH=1 \
    sh
  UV_BIN="${UV_INSTALL_DIR}/uv"
fi

"$UV_BIN" sync --extra dev --frozen
.venv/bin/python -m pytest --version
bash scripts/cursor/cloud-bootstrap.sh
