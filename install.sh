#!/usr/bin/env bash
# =============================================================================
# Perpetua-Tools install.sh — Layer-2 middleware bootstrap
# =============================================================================
# Installs Claude Desktop LLM extensions (real MCPB from vendor submodule) by default.
# Does not require AlphaClaw. Claude Code MCP: packages/alphaclaw-mcp (separate).
#
# Usage:
#   bash install.sh                    # submodule + build MCPB + stage bundles + guided vendor install
#   bash install.sh --open             # also open .mcpb on macOS (Claude Desktop UI)
#   bash install.sh --skip-mcpb        # skip Desktop LLM (submodule init only)
#   bash install.sh --skip-desktop     # forwarded to install-claude-desktop-llm.sh
#   bash install.sh --skip-vendor-guide  # skip the entire guided vendor/ step
#   bash install.sh --skip-hygiene-check --skip-ecc --skip-agentic-stack --skip-autoresearch
#                                         # skip any/all of the 4 guided sub-steps individually
#   bash install.sh --non-interactive    # run the guided step without prompting (CI-safe)
#   bash install.sh --help
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKIP_MCPB=0
SKIP_VENDOR_GUIDE=0
NON_INTERACTIVE=0
GUIDE_SKIP_ARGS=()
EXTRA_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --skip-mcpb) SKIP_MCPB=1 ;;
    --skip-vendor-guide) SKIP_VENDOR_GUIDE=1 ;;
    --non-interactive) NON_INTERACTIVE=1 ;;
    --skip-hygiene-check|--skip-ecc|--skip-agentic-stack|--skip-autoresearch)
      GUIDE_SKIP_ARGS+=("$arg") ;; # forwarded to install-vendor-guided.sh only
    --skip-desktop) EXTRA_ARGS+=("$arg") ;; # forwarded to install-claude-desktop-llm.sh
    --help|-h)
      echo "Usage: install.sh [--open] [--skip-mcpb] [--skip-desktop] [--skip-vendor-guide]"
      echo "                  [--skip-hygiene-check] [--skip-ecc] [--skip-agentic-stack]"
      echo "                  [--skip-autoresearch] [--non-interactive] [--help]"
      echo "  Default: init vendor/Claude-Desktop-LLM, build MCPB bundles, then run the"
      echo "  guided vendor/ install (ecc-tools, agentic-stack, autoresearch — idempotent,"
      echo "  asks before touching anything ambiguous). Every guided sub-step is individually"
      echo "  skippable; --skip-vendor-guide skips all of them at once."
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

if [[ "$SKIP_VENDOR_GUIDE" -eq 0 ]]; then
  guide_args=("${GUIDE_SKIP_ARGS[@]}")
  [[ "$NON_INTERACTIVE" -eq 1 ]] && guide_args+=(--non-interactive)
  bash "$SCRIPT_DIR/scripts/install-vendor-guided.sh" "${guide_args[@]}"
else
  echo ""
  echo "  (skipped guided vendor install — --skip-vendor-guide)"
fi

echo ""
echo "Done. Claude Code: cd packages/alphaclaw-mcp && npm run build"
echo "      claude mcp add --transport stdio alphaclaw -- node packages/alphaclaw-mcp/build/index.js"
