#!/usr/bin/env bash
# Cursor sessionStart hook — apply git guards outside any single repo checkout.
# Installed to ~/.cursor/openclaw/hooks/ by install-user-git-environment.sh
set -euo pipefail

HOME="${HOME:-/home/ubuntu}"
export HOME
OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/openclaw-v1}"

input="$(cat)"

find_orama_root() {
  local root
  while IFS= read -r root; do
    [[ -n "$root" ]] || continue
    if [[ -x "$root/scripts/git/apply-attribution-guard-all-repos.sh" ]]; then
      printf '%s\n' "$root"
      return 0
    fi
  done
  return 1
}

resolve_orama_from_pt_root() {
  local root resolved
  while IFS= read -r root; do
    [[ -n "$root" ]] || continue
    [[ -f "$root/scripts/resolve_orama_root.sh" ]] || continue
    resolved="$(cd "$root" && source scripts/resolve_orama_root.sh >/dev/null 2>&1 && resolve_orama_root 2>/dev/null || true)"
    if [[ -n "$resolved" && -x "$resolved/scripts/git/apply-attribution-guard-all-repos.sh" ]]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done
  return 1
}

mapfile -t workspace_roots < <(
  ORAMA_SYSTEM_PATH="${ORAMA_SYSTEM_PATH:-}" \
  REPO_ROOT="${REPO_ROOT:-}" \
  OPENCLAW_HOME="$OPENCLAW_HOME" \
  python3 -c '
import json, os, sys

raw = sys.stdin.read()
try:
    data = json.loads(raw) if raw.strip() else {}
except json.JSONDecodeError:
    data = {}

roots = list(data.get("workspace_roots") or [])
for env_key in ("ORAMA_SYSTEM_PATH", "REPO_ROOT"):
    val = os.environ.get(env_key, "").strip()
    if val:
        roots.append(val)
roots.extend(("/workspace", os.path.expanduser("~/workspace")))
seen = set()
out = []
for r in roots:
    if not r:
        continue
    abs_r = os.path.abspath(os.path.expanduser(r))
    if abs_r in seen:
        continue
    seen.add(abs_r)
    out.append(abs_r)
print("\n".join(out))
' <<<"$input"
)

orama="$({
  for r in "${workspace_roots[@]}"; do printf '%s\n' "$r"; done
} | resolve_orama_from_pt_root || true)"

if [[ -z "$orama" ]]; then
  orama="$({
  for r in "${workspace_roots[@]}"; do printf '%s\n' "$r"; done
  printf '%s\n' "${ORAMA_SYSTEM_PATH:-}" "${REPO_ROOT:-}" "/workspace"
  } | find_orama_root || true)"
fi

if [[ -n "$orama" ]]; then
  export ORAMA_SYSTEM_PATH="$orama"
  export PERPETUA_TOOLS_PATH="${PERPETUA_TOOLS_PATH:-$OPENCLAW_HOME/Perpetua-Tools}"
  export ALPHACLAW_INSTALL_DIR="${ALPHACLAW_INSTALL_DIR:-$OPENCLAW_HOME/AlphaClaw}"
  bash "$orama/scripts/git/apply-attribution-guard-all-repos.sh" || true
else
  user_apply="${HOME}/.cursor/openclaw/git-guards/apply-all-repos.sh"
  if [[ -x "$user_apply" ]]; then
    bash "$user_apply" || true
  fi
fi

# Per-workspace: disable Cursor co-author hook + install .githooks when present.
for root in "${workspace_roots[@]}"; do
  [[ -d "$root/.git" ]] || continue
  ws_id="$(printf '%s' "$root" | python3 -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode().rstrip("="))')"
  coauthor="${HOME}/.cursor/agent-hooks/${ws_id}/commit-msg.cursor.co-author"
  if [[ -f "$coauthor" ]]; then
    chmod -x "$coauthor" 2>/dev/null || true
  fi
  if [[ -x "$root/scripts/git/install-local-hooks.sh" ]]; then
    bash "$root/scripts/git/install-local-hooks.sh" || true
  fi
  git -C "$root" config --local user.name "cyre" 2>/dev/null || true
  git -C "$root" config --local user.email "diazMelgarejo@gmail.com" 2>/dev/null || true
done

exit 0
