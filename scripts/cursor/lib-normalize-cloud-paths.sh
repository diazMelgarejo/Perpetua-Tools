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

  # Use prefix slicing — do NOT use [[ == ~/* ]] or case ~/*) patterns:
  # bash tilde-expands those patterns and breaks literal "~/..." handling.
  if [[ "$raw" == "~" ]]; then
    printf '%s\n' "$home"
    return 0
  fi
  if [[ "${raw:0:2}" == '~/' ]]; then
    printf '%s\n' "$home/${raw:2}"
    return 0
  fi
  if [[ "$raw" == '$HOME' ]]; then
    printf '%s\n' "$home"
    return 0
  fi
  if [[ "${raw:0:6}" == '$HOME/' ]]; then
    printf '%s\n' "$home/${raw:6}"
    return 0
  fi

  printf '%s\n' "$raw"
}

_path_is_junk_checkout() {
  local path="$1"
  local repo_root="${2:-}"

  [[ "$path" == *"/~/"* ]] && return 0
  if [[ -n "$repo_root" ]]; then
    case "$path" in
      "$repo_root" | "$repo_root"/*) return 0 ;;
    esac
  fi
  return 1
}

_default_sibling_path() {
  local var_name="$1"
  local repo_root="${2:-}"
  local openclaw_home="$3"
  local repo_base=""

  if [[ -n "$repo_root" ]]; then
    repo_base="$(basename "$repo_root")"
  fi

  case "$var_name" in
    ORAMA_SYSTEM_PATH)
      if [[ "$repo_base" == "orama-system" ]]; then
        printf '%s\n' "$repo_root"
      else
        printf '%s\n' "$openclaw_home/orama-system"
      fi
      ;;
    PERPETUA_TOOLS_PATH)
      if [[ "$repo_base" == "Perpetua-Tools" ]]; then
        printf '%s\n' "$repo_root"
      else
        printf '%s\n' "$openclaw_home/Perpetua-Tools"
      fi
      ;;
    ALPHACLAW_INSTALL_DIR)
      if [[ "$repo_base" == "AlphaClaw" ]]; then
        printf '%s\n' "$repo_root"
      else
        printf '%s\n' "$openclaw_home/AlphaClaw"
      fi
      ;;
  esac
}

_normalize_sibling_path() {
  local var_name="$1"
  local raw="${2:-}"
  local repo_root="${3:-}"
  local openclaw_home="${4:-}"

  if [[ -z "$raw" ]]; then
    return 0
  fi

  raw="$(_normalize_user_path "$raw")"
  if _path_is_junk_checkout "$raw" "$repo_root"; then
    raw="$(_default_sibling_path "$var_name" "$repo_root" "$openclaw_home")"
  fi
  printf '%s\n' "$raw"
}

normalize_cloud_openclaw_paths() {
  local home="${HOME:-/home/ubuntu}"
  local repo_root="${REPO_ROOT:-}"
  local normalized
  local sibling

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
    sibling="$(_normalize_sibling_path ORAMA_SYSTEM_PATH "$ORAMA_SYSTEM_PATH" "$repo_root" "$normalized")"
    export ORAMA_SYSTEM_PATH="$sibling"
  fi
  if [[ -n "${PERPETUA_TOOLS_PATH:-}" ]]; then
    sibling="$(_normalize_sibling_path PERPETUA_TOOLS_PATH "$PERPETUA_TOOLS_PATH" "$repo_root" "$normalized")"
    export PERPETUA_TOOLS_PATH="$sibling"
  fi
  if [[ -n "${ALPHACLAW_INSTALL_DIR:-}" ]]; then
    sibling="$(_normalize_sibling_path ALPHACLAW_INSTALL_DIR "$ALPHACLAW_INSTALL_DIR" "$repo_root" "$normalized")"
    export ALPHACLAW_INSTALL_DIR="$sibling"
  fi
}
