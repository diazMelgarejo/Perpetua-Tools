#!/usr/bin/env bash
# scripts/ensure_requirements.sh — idempotent requirements probe + installer
# Perpetua-Tools v0.9.9.8 (Layer 2 — middleware/adapters)
#
# Soft requirements (auto-install):
#   Python venv + pip deps (sha256-stamped, skips if unchanged)
#   Node packages: packages/alphaclaw-adapter, packages/alphaclaw-mcp
#
# Hard requirements (Ollama + models) live in orama-system/scripts/ensure_requirements.sh.
# PT's only hard advisory: LM_STUDIO_WIN_ENDPOINTS env must be set for Win routing.
#
# Platform support: Linux, macOS, Docker (bash). Windows: see ensure_requirements.ps1
#
# Usage:
#   bash scripts/ensure_requirements.sh            # check + install
#   bash scripts/ensure_requirements.sh --check    # probe only, exit 1 if hard missing
#   bash scripts/ensure_requirements.sh --force    # skip stamps, reinstall everything
#   bash scripts/ensure_requirements.sh --quiet    # suppress INFO lines
#
# Env overrides:
#   ORAMA_SKIP_ENSURE=1   — bypass entirely
#   LM_STUDIO_WIN_ENDPOINTS — Win LM Studio URL (advisory check)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${PT_VENV_DIR:-${SCRIPT_DIR}/.venv}"
VENV_PYTHON="${VENV_DIR}/bin/python"
STAMP_FILE="${VENV_DIR}/.pt-requirements.stamp"
LOG_DIR="${SCRIPT_DIR}/.logs"
mkdir -p "$LOG_DIR"

MODE_CHECK=0; MODE_FORCE=0; MODE_QUIET=0
for _arg in "$@"; do
  case "$_arg" in
    --check) MODE_CHECK=1 ;;
    --force) MODE_FORCE=1 ;;
    --quiet) MODE_QUIET=1 ;;
  esac
done

_ts()   { date +%H:%M:%S; }
_info() { [ "$MODE_QUIET" -eq 0 ] && echo "[$(_ts)] INFO  [pt-ensure] $*" || true; }
_warn() { echo "[$(_ts)] WARN  [pt-ensure] $*" >&2; }
_err()  { echo "[$(_ts)] ERROR [pt-ensure] $*" >&2; }
_ok()   { echo "[$(_ts)] OK    [pt-ensure] $*"; }

_OS="$(uname -s 2>/dev/null || echo Unknown)"
_ARCH="$(uname -m 2>/dev/null || echo unknown)"
_IS_DOCKER=0; [ -f "/.dockerenv" ] && _IS_DOCKER=1

_hash_text() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | awk '{print $1}'
  else
    echo "none"
  fi
}

_hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    echo "none"
  fi
}

_req_hash() {
  local name file manifest="source:${SCRIPT_DIR}\n"
  for name in requirements.txt pyproject.toml uv.lock; do
    file="${SCRIPT_DIR}/${name}"
    [ -f "$file" ] || continue
    manifest="${manifest}${name}:$(_hash_file "$file")\n"
  done
  [ -n "$manifest" ] && printf '%b' "$manifest" | _hash_text || echo "none"
}
_stamp_current() { cat "$STAMP_FILE" 2>/dev/null | grep "^python_req=" | cut -d= -f2 || echo ""; }
_stamp_write() {
  { echo "python_req=$(_req_hash)"; echo "ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "version=1"; } > "$STAMP_FILE"
}

_info "Platform: ${_OS} ${_ARCH}$( [ "$_IS_DOCKER" -eq 1 ] && echo " (Docker)" || true )"

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Advisory: LM Studio Win endpoint
# ──────────────────────────────────────────────────────────────────────────────
_info "Phase 1 — LM Studio Win endpoint (advisory)"

if [ -z "${LM_STUDIO_WIN_ENDPOINTS:-}" ]; then
  _warn "LM_STUDIO_WIN_ENDPOINTS not set — Windows GPU routing unavailable"
  _warn "Set in .env or: export LM_STUDIO_WIN_ENDPOINTS=http://<win-ip>:1234"
  _warn "See CLAUDE-instru.md §6. On Windows: run scripts/ensure_requirements.ps1"
else
  # Quick reachability probe (1s timeout, non-fatal)
  if curl -sf --max-time 1 "${LM_STUDIO_WIN_ENDPOINTS}/v1/models" >/dev/null 2>&1; then
    _ok "LM Studio Win reachable at ${LM_STUDIO_WIN_ENDPOINTS}"
  else
    _warn "LM Studio Win not reachable at ${LM_STUDIO_WIN_ENDPOINTS} — Win GPU routing will fail"
    _warn "Start LM Studio on Windows, enable local server on port 1234, load a model"
  fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Python venv + pip deps (sha256-stamped)
# ──────────────────────────────────────────────────────────────────────────────
_info "Phase 2 — Python venv + dependencies"

VENV_FRESH=0
if ! "$VENV_PYTHON" -c 'import sys; assert sys.prefix != sys.base_prefix' >/dev/null 2>&1; then
  if [ "$MODE_CHECK" -eq 0 ]; then
    _info "Creating Python venv..."
    python3 -m venv "$VENV_DIR" >>"${LOG_DIR}/install.log" 2>&1 \
      || { _err "venv creation failed — see ${LOG_DIR}/install.log"; exit 1; }
    VENV_FRESH=1
  else
    _err "Working venv not found at PT_VENV_DIR — run without --check to create"
    exit 1
  fi
else
  _ok "Python venv exists"
fi

if [ -x "$VENV_PYTHON" ]; then
  CURRENT_HASH="$(_stamp_current)"
  EXPECTED_HASH="$(_req_hash)"
  if [ "$MODE_FORCE" -eq 1 ] || [ "$VENV_FRESH" -eq 1 ] || [ "$CURRENT_HASH" != "$EXPECTED_HASH" ]; then
    if [ "$MODE_CHECK" -eq 0 ]; then
      _info "Installing Python deps (dependency contract changed)..."
      _pip_ok=0
      if "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
        (cd "$SCRIPT_DIR" && "$VENV_PYTHON" -m pip install -q -r requirements.txt) \
          >>"${LOG_DIR}/install.log" 2>&1 && _pip_ok=1
      elif command -v uv >/dev/null 2>&1; then
        (cd "$SCRIPT_DIR" && uv pip install --python "$VENV_PYTHON" -q -r requirements.txt) \
          >>"${LOG_DIR}/install.log" 2>&1 && _pip_ok=1
      fi
      if [ "$_pip_ok" -eq 1 ]; then
        _stamp_write
        _ok "Python deps installed (stamp updated)"
      else
        _err "Dependency installation failed; use python -m ensurepip or install uv; see ${LOG_DIR}/install.log"
        exit 1
      fi
    else
      _warn "dependency contract hash mismatch — run without --check to update"
      exit 1
    fi
  else
    _ok "Python deps up-to-date (stamp matches)"
  fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Node packages for PT adapter packages
# ──────────────────────────────────────────────────────────────────────────────
_info "Phase 3 — Node packages"

# Require Node 20+
_NODE_OK=0
if command -v node >/dev/null 2>&1; then
  _NODE_MAJOR="$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1 || echo 0)"
  if [ "$_NODE_MAJOR" -ge 20 ] 2>/dev/null; then
    _NODE_OK=1
    _ok "Node.js v$_NODE_MAJOR present"
  else
    _warn "Node.js v$_NODE_MAJOR found — Node 20+ required for alphaclaw packages"
  fi
else
  _warn "Node.js not in PATH — alphaclaw Node packages will not be installed"
  _warn "Install Node 20+: https://nodejs.org or: brew install node"
fi

if [ "$_NODE_OK" -eq 1 ]; then
  NODE_PACKAGES=(
    "packages/alphaclaw-adapter"
    "packages/alphaclaw-mcp"
  )

  for pkg_rel in "${NODE_PACKAGES[@]}"; do
    PKG_DIR="${SCRIPT_DIR}/${pkg_rel}"
    [ -d "$PKG_DIR" ] || { _info "${pkg_rel}: directory not found — skipping"; continue; }
    PKG_JSON="${PKG_DIR}/package.json"
    [ -f "$PKG_JSON" ] || { _info "${pkg_rel}: no package.json — skipping"; continue; }

    NODE_MODULES="${PKG_DIR}/node_modules"
    PKG_STAMP="${PKG_DIR}/.node_stamp"
    PKG_HASH="$(_hash_file "$PKG_JSON")"
    STAMP_HASH="$(cat "$PKG_STAMP" 2>/dev/null || echo "")"

    if [ ! -d "$NODE_MODULES" ] || [ "$MODE_FORCE" -eq 1 ] || [ "$STAMP_HASH" != "$PKG_HASH" ]; then
      if [ "$MODE_CHECK" -eq 0 ]; then
        _info "${pkg_rel}: installing Node deps..."
        (cd "$PKG_DIR" && npm install --package-lock=false --silent >>"${LOG_DIR}/install.log" 2>&1) && {
          echo "$PKG_HASH" > "$PKG_STAMP"
          _ok "${pkg_rel}: Node deps installed"
        } || { _err "${pkg_rel}: npm install failed — see ${LOG_DIR}/install.log"; exit 1; }
      else
        [ ! -d "$NODE_MODULES" ] \
          && _warn "${pkg_rel}/node_modules missing — run without --check" \
          || _warn "${pkg_rel}: package.json changed — run without --check to update"
      fi
    else
      _ok "${pkg_rel}: up-to-date"
    fi
  done
fi

# ──────────────────────────────────────────────────────────────────────────────
# RESULT
# ──────────────────────────────────────────────────────────────────────────────
echo ""
_ok "Perpetua-Tools requirements check complete"
echo ""
exit 0
