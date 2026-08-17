#!/usr/bin/env bash
# scripts/install-vendor-guided.sh — guided, idempotent vendor/ submodule bootstrap.
#
# Encodes the manual walkthrough from the 2026-07-11 session so future runs
# (and other machines) don't need a human to re-derive it by hand:
#
#   1. Init all vendor/ submodules (idempotent)
#   2. Hygiene check: any git-index gitlink with no .gitmodules mapping -> warn
#      (this is how packages/agentic-stack, an orphaned pre-rename duplicate,
#       was found and fixed — see git log d13cd570)
#   3. ecc-tools: detect existing global/project install; if neither exists,
#      ask which profile to install (interactive) or print the exact command
#      to run (non-interactive) — never guess a profile for the user's real
#      ~/.claude
#   4. agentic-stack: delegate to scripts/git/install-agentic-stack.sh, which
#      is already idempotent and dry-run-safe (doc: orama-system
#      docs/v2/41-agentic-stack-gstack-gbrain-memory-blend.md)
#   5. autoresearch: install globally if absent; if a global install exists
#      but drifts from the vendored source, ask before overwriting instead of
#      silently clobbering (install.sh's own sync_dir does `rm -rf` first)
#
# Every step is safe to re-run. Nothing here writes to vendor/ itself.
#
# Usage:
#   bash scripts/install-vendor-guided.sh              # interactive when a TTY is attached
#   bash scripts/install-vendor-guided.sh --non-interactive
#       # never prompts; prints the exact follow-up command for anything
#       # that needs a human decision, then continues
#   bash scripts/install-vendor-guided.sh --skip-hygiene-check --skip-ecc \
#       --skip-agentic-stack --skip-autoresearch
#       # skip any/all of the 4 steps individually; submodule init (step 1)
#       # always runs since everything else depends on it
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORCE_NON_INTERACTIVE=0
SKIP_HYGIENE=0
SKIP_ECC=0
SKIP_AGENTIC_STACK=0
SKIP_AUTORESEARCH=0

for arg in "$@"; do
  case "$arg" in
    --non-interactive) FORCE_NON_INTERACTIVE=1 ;;
    --skip-hygiene-check) SKIP_HYGIENE=1 ;;
    --skip-ecc) SKIP_ECC=1 ;;
    --skip-agentic-stack) SKIP_AGENTIC_STACK=1 ;;
    --skip-autoresearch) SKIP_AUTORESEARCH=1 ;;
  esac
done

_is_interactive() {
  [[ "$FORCE_NON_INTERACTIVE" -eq 0 && -t 0 && -t 1 ]]
}

echo ""
echo "Vendor submodules — guided install"
echo "───────────────────────────────────"

echo "[1/5] Initializing all vendor/ submodules..."
git -C "$REPO_ROOT" submodule update --init --recursive

echo ""
echo "[2/5] Checking for orphaned gitlinks (tracked but missing from .gitmodules)..."
if [[ "$SKIP_HYGIENE" -eq 1 ]]; then
  echo "  skipped (--skip-hygiene-check)"
else
_check_orphaned_gitlinks() {
  local declared actual orphans
  declared="$(git -C "$REPO_ROOT" config -f "$REPO_ROOT/.gitmodules" --get-regexp '\.path$' 2>/dev/null | awk '{print $2}' | sort)"
  actual="$(git -C "$REPO_ROOT" ls-files -s | awk '$1=="160000"{print $4}' | sort)"
  orphans="$(comm -13 <(printf '%s\n' "$declared") <(printf '%s\n' "$actual") 2>/dev/null || true)"
  if [[ -n "$orphans" ]]; then
    echo "  WARN: gitlink(s) tracked in the index but not declared in .gitmodules:"
    printf '%s\n' "$orphans" | sed 's/^/    /'
    echo "    fix (keeps files on disk): git rm --cached <path>"
  else
    echo "  clean — every tracked gitlink has a .gitmodules mapping"
  fi
}
_check_orphaned_gitlinks
fi

echo ""
echo "[3/5] ecc-tools..."
if [[ "$SKIP_ECC" -eq 1 ]]; then
  echo "  skipped (--skip-ecc)"
else
_ecc_status() {
  local global_dir="$HOME/.claude" project_dir="$REPO_ROOT/.claude"
  local has_global=0 has_project=0
  [[ -d "$global_dir/rules/ecc" || -d "$global_dir/skills/ecc" ]] && has_global=1
  [[ -d "$project_dir/rules/ecc" || -d "$project_dir/skills/ecc" ]] && has_project=1

  if [[ $has_global -eq 1 && $has_project -eq 0 ]]; then
    echo "  already installed globally (~/.claude) — nothing to do"
    return
  fi
  if [[ $has_global -eq 1 && $has_project -eq 1 ]]; then
    echo "  BOTH a global and a project-bound install exist — needs manual review, not auto-resolved."
    echo "    policy: project-bound installs should become thin wrappers pointing at global."
    return
  fi
  if [[ $has_project -eq 1 && $has_global -eq 0 ]]; then
    echo "  project-bound install found at .claude/ but no global install."
    echo "    policy: move to global first, then make the project copy a thin wrapper."
    echo "    run manually — this migration needs human judgment on what to preserve:"
    echo "      bash vendor/ecc-tools/install.sh --target claude --profile <profile>"
    return
  fi
  # neither exists
  echo "  no ecc-tools install found (profiles: minimal, opencode, core, developer, security, research, full)"
  if _is_interactive; then
    read -r -p "  install profile globally now? [developer/minimal/core/security/research/full/skip] (developer): " profile
    profile="${profile:-developer}"
    if [[ "$profile" == "skip" ]]; then
      echo "  skipped"
      return
    fi
    bash "$REPO_ROOT/vendor/ecc-tools/install.sh" --target claude --profile "$profile"
  else
    echo "  (non-interactive — run: bash vendor/ecc-tools/install.sh --target claude --profile developer)"
  fi
}
_ecc_status

_antigravity_gemini_status() {
  local agy_dir="$HOME/.antigravity" gemini_dir="$HOME/.gemini"
  if [[ -d "$agy_dir" || -d "$gemini_dir" ]]; then
    echo "  AntiGravity / Gemini environment detected — ensuring harmonized overlay..."
    if [[ -d "$agy_dir" && ! -f "$agy_dir/ANTIGRAVITY.md" ]]; then
      if [[ -f "$REPO_ROOT/vendor/ecc-tools/.antigravity/ANTIGRAVITY.md" ]]; then
        install -m 0644 "$REPO_ROOT/vendor/ecc-tools/.antigravity/ANTIGRAVITY.md" "$agy_dir/ANTIGRAVITY.md" 2>/dev/null || true
        echo "    ✓ synthesized ~/.antigravity/ANTIGRAVITY.md overlay"
      fi
    fi
  fi
}
_antigravity_gemini_status
fi

echo ""
echo "[4/5] agentic-stack..."
if [[ "$SKIP_AGENTIC_STACK" -eq 1 ]]; then
  echo "  skipped (--skip-agentic-stack)"
else
  bash "$REPO_ROOT/scripts/git/install-agentic-stack.sh"
fi

echo ""
echo "[5/5] autoresearch..."
if [[ "$SKIP_AUTORESEARCH" -eq 1 ]]; then
  echo "  skipped (--skip-autoresearch)"
else
_autoresearch_status() {
  local global_dir="$HOME/.claude/skills/autoresearch"
  local src="$REPO_ROOT/vendor/autoresearch/.claude/skills/autoresearch"
  if [[ ! -d "$global_dir" ]]; then
    echo "  not installed globally — installing now"
    bash "$REPO_ROOT/vendor/autoresearch/scripts/install.sh" --claude --global --force
    return
  fi
  if diff -rq "$global_dir" "$src" >/dev/null 2>&1; then
    echo "  already installed globally, up to date"
    return
  fi
  echo "  global install DRIFTS from the vendored source."
  if _is_interactive; then
    read -r -p "  overwrite global with vendored source? [y/N] " ans
    if [[ "$ans" =~ ^[Yy] ]]; then
      bash "$REPO_ROOT/vendor/autoresearch/scripts/install.sh" --claude --global --force
    else
      echo "  left as-is"
    fi
  else
    echo "  (non-interactive — review the diff, then: bash vendor/autoresearch/scripts/install.sh --claude --global --force)"
  fi
}
_autoresearch_status
fi

echo ""
echo "Vendor guided install: done."
