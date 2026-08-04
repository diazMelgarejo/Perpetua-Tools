#!/usr/bin/env bash
# Normalize Cursor Cloud path env vars so literal "~" / "$HOME" never create
# nested trees like <repo>/~/openclaw-v1 (tilde is not expanded inside "...$VAR").
#
# Source from cloud-install / cloud-attribution-bootstrap / install-user hooks:
#   # shellcheck source=lib-normalize-cloud-paths.sh
#   source "$(dirname "${BASH_SOURCE[0]}")/lib-normalize-cloud-paths.sh"
#   normalize_cloud_openclaw_paths
#
# Safe to source multiple times.

_normalize_user_path() {
  local raw="${1:-}"
  local home="${HOME:-/home/ubuntu}"

  case "$raw" in
    "" | "/" | "/openclaw-v1" | '$HOME/openclaw-v1' | '~/openclaw-v1')
      printf '%s\n' "$home/openclaw-v1"
      return 0
      ;;
  esac

  if [[ "$raw" == "~" ]]; then
    printf '%s\n' "$home"
    return 0
  fi
  if [[ "$raw" == "~/"* ]]; then
    printf '%s\n' "$home/${raw#~/}"
    return 0
  fi
  if [[ "$raw" == '$HOME' ]]; then
    printf '%s\n' "$home"
    return 0
  fi
  if [[ "$raw" == '$HOME/'* ]]; then
    printf '%s\n' "$home/${raw#\$HOME/}"
    return 0
  fi

  printf '%s\n' "$raw"
}

normalize_cloud_openclaw_paths() {
  local home="${HOME:-/home/ubuntu}"
  local repo_root="${REPO_ROOT:-}"
  local normalized

  HOME="$home"
  export HOME

  normalized="$(_normalize_user_path "${OPENCLAW_HOME:-}")"
  # Refuse an OPENCLAW_HOME that resolves inside the primary checkout — that is
  # how literal "~/openclaw-v1" created orama-system/~/openclaw-v1 clones.
  if [[ -n "$repo_root" ]]; then
    case "$normalized" in
      "$repo_root" | "$repo_root"/*)
        normalized="$home/openclaw-v1"
        ;;
    esac
  fi
  export OPENCLAW_HOME="$normalized"

  if [[ -n "${ORAMA_SYSTEM_PATH:-}" ]]; then
    export ORAMA_SYSTEM_PATH="$(_normalize_user_path "$ORAMA_SYSTEM_PATH")"
  fi
  if [[ -n "${PERPETUA_TOOLS_PATH:-}" ]]; then
    export PERPETUA_TOOLS_PATH="$(_normalize_user_path "$PERPETUA_TOOLS_PATH")"
  fi
  if [[ -n "${ALPHACLAW_INSTALL_DIR:-}" ]]; then
    export ALPHACLAW_INSTALL_DIR="$(_normalize_user_path "$ALPHACLAW_INSTALL_DIR")"
  fi
}
