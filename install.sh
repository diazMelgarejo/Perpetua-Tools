#!/usr/bin/env bash
# =============================================================================
# Perpetua-Tools install.sh — Layer-2 middleware bootstrap
# =============================================================================
# Installs Claude Desktop LLM extensions (real MCPB from vendor submodule) by default.
# Does not require AlphaClaw. Claude Code MCP: packages/alphaclaw-mcp (separate).
#
# Windows companion: install.ps1 (same flags; mesh via Invoke-MeshLocalCache.ps1)
#
# Usage:
#   bash install.sh                    # submodule + build MCPB + stage bundles
#   bash install.sh --open             # also open .mcpb on macOS (Claude Desktop UI)
#   bash install.sh --skip-mcpb        # skip Desktop LLM (submodule init only)
#   bash install.sh --skip-desktop     # forwarded to install-claude-desktop-llm.sh
#   bash install.sh --vendor-guide     # additionally run guided vendor/ bootstrap
#   bash install.sh --skip-vendor-guide  # compatibility no-op; guide is opt-in
#   bash install.sh --skip-hygiene-check --skip-ecc --skip-agentic-stack --skip-autoresearch
#                                         # skip guided sub-steps when --vendor-guide is used
#   bash install.sh --non-interactive  # make --vendor-guide non-interactive/CI-safe
#   bash install.sh --help
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKIP_MCPB=0
RUN_VENDOR_GUIDE=0
NON_INTERACTIVE=0
GUIDE_SKIP_ARGS=()
EXTRA_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --skip-mcpb) SKIP_MCPB=1 ;;
    --vendor-guide) RUN_VENDOR_GUIDE=1 ;;
    --skip-vendor-guide) RUN_VENDOR_GUIDE=0 ;;
    --non-interactive) NON_INTERACTIVE=1 ;;
    --skip-hygiene-check|--skip-ecc|--skip-agentic-stack|--skip-autoresearch)
      GUIDE_SKIP_ARGS+=("$arg") ;; # forwarded only when --vendor-guide is enabled
    --skip-desktop) EXTRA_ARGS+=("$arg") ;; # forwarded to install-claude-desktop-llm.sh
    --help|-h)
      echo "Usage: install.sh [--open] [--skip-mcpb] [--skip-desktop] [--vendor-guide]"
      echo "                  [--skip-vendor-guide] [--skip-hygiene-check] [--skip-ecc]"
      echo "                  [--skip-agentic-stack] [--skip-autoresearch]"
      echo "                  [--non-interactive] [--help]"
      echo "  Default: init vendor/Claude-Desktop-LLM and build/stage MCPB bundles."
      echo "  --vendor-guide opts into the broader vendor bootstrap (ecc-tools,"
      echo "  agentic-stack, autoresearch). Guided sub-steps are individually skippable."
      exit 0
      ;;
    *) EXTRA_ARGS+=("$arg") ;;
  esac
done

echo ""
echo "Perpetua-Tools install"
echo "──────────────────────"

if ! git -C "$SCRIPT_DIR" submodule update --init --recursive vendor/Claude-Desktop-LLM; then
  echo "Failed to init submodule vendor/Claude-Desktop-LLM" >&2
  exit 1
fi

if [[ "$SKIP_MCPB" -eq 0 ]]; then
  bash "$SCRIPT_DIR/scripts/install-claude-desktop-llm.sh" "${EXTRA_ARGS[@]}"
else
  echo "  (skipped MCPB build — --skip-mcpb)"
fi

MESH_DIR="$SCRIPT_DIR/scripts/mesh"
if [[ -f "$MESH_DIR/ensure_local_mesh_secrets.py" ]]; then
  python3 "$MESH_DIR/ensure_local_mesh_secrets.py" \
    || echo "  warn: GOSSIP_SHARED_SECRET not written — run ensure_local_mesh_secrets.py manually" >&2
fi
# Win parity: scripts/mesh/Invoke-MeshLocalCache.ps1 (install.ps1 -Mode Install)

# Layer-3 macOS pf egress verification (non-blocking warning)
if [[ "$(uname -s 2>/dev/null || echo Unknown)" == "Darwin" ]] && [[ -f "$SCRIPT_DIR/scripts/security/verify-egress-pf-rules.sh" ]]; then
  if ! bash "$SCRIPT_DIR/scripts/security/verify-egress-pf-rules.sh" >/dev/null 2>&1; then
    echo "  warn: Layer-3 macOS pf egress rules not active — run: sudo bash scripts/security/install-egress-pf-rules.sh" >&2
  fi
fi

if [[ "$RUN_VENDOR_GUIDE" -eq 1 ]]; then
  guide_args=("${GUIDE_SKIP_ARGS[@]}")
  [[ "$NON_INTERACTIVE" -eq 1 ]] && guide_args+=(--non-interactive)
  bash "$SCRIPT_DIR/scripts/install-vendor-guided.sh" "${guide_args[@]}"
else
  echo ""
  echo "  (guided vendor install not requested — use --vendor-guide)"
fi

echo ""
echo "Done. Claude Code: cd packages/alphaclaw-mcp && npm run build"
echo "      claude mcp add --transport stdio alphaclaw -- node packages/alphaclaw-mcp/build/index.js"
