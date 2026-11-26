#!/usr/bin/env bash
# install-openclaw-runtime.sh — reproduce the OpenClaw + AlphaClaw runtime baseline of 2026-11-25.
#
# Steps, in dependency order (each is idempotent and skips what is already right):
#   1 node      the nvm node that satisfies AlphaClaw/openclaw engines (>=24.22.1 <25), set as the nvm default
#   2 openclaw  the global openclaw pinned by AlphaClaw, installed under that node
#   3 alphaclaw the fork build (PR 34 tarball) installed into ~/.alphaclaw, old @chrysb package removed
#   4 link      the stable node link and the launch agent that uses it (perpetua_tools.openclaw_runtime)
#   5 gateway   OPT-IN only (--fresh-gateway --accept-risk): move ~/.openclaw aside, onboard fresh on loopback
#
# Usage:
#   bash scripts/install-openclaw-runtime.sh                 # --check: read-only, exits 1 on drift
#   bash scripts/install-openclaw-runtime.sh --plan  [opts]  # print the exact commands, run nothing
#   bash scripts/install-openclaw-runtime.sh --apply [opts]  # run them
# Options:
#   --node VERSION               default 24.22.3
#   --openclaw VERSION           default: the version the installed AlphaClaw pins, else 2026.10.6
#   --migrate-globals-from V     carry global npm packages over from node V (nvm --reinstall-packages-from)
#   --alphaclaw-tarball PATH     the packed fork build; without it step 3 only reports
#   --fresh-gateway --accept-risk  step 5; the second flag acknowledges that agents have powerful system access
#
# After step 5 restore state in baby steps, one stage at a time with a gateway check after each:
# core config, agents and workspace, the W&B default, fallback providers, plugins one at a time, Telegram last.
# See docs/openclaw-setup.md. Bash 3.2 compatible.
set -euo pipefail

MODE="check"
NODE_VER="24.22.3"
OPENCLAW_VER=""
EXPLICIT_OPENCLAW=0
MIGRATE_FROM=""
TARBALL=""
FRESH=0
ACCEPT=0
DEFAULT_OPENCLAW="2026.10.6"
PORT="18789"
PT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NVM_HOME="${NVM_DIR:-$HOME/.nvm}"

usage() { awk 'NR > 1 { if (!/^#/) exit; sub(/^# ?/, ""); print }' "$0"; }
die() { echo "install-openclaw-runtime: $*" >&2; exit 2; }
need() { [ "$#" -ge 2 ] || die "$1 needs a value"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE="check" ;;
    --plan) MODE="plan" ;;
    --apply) MODE="apply" ;;
    --node) need "$@"; NODE_VER="$2"; shift ;;
    --openclaw) need "$@"; OPENCLAW_VER="$2"; EXPLICIT_OPENCLAW=1; shift ;;
    --migrate-globals-from) need "$@"; MIGRATE_FROM="$2"; shift ;;
    --alphaclaw-tarball) need "$@"; TARBALL="$2"; shift ;;
    --fresh-gateway) FRESH=1 ;;
    --accept-risk) ACCEPT=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

if [ "$FRESH" = "1" ] && [ "$ACCEPT" != "1" ]; then
  die "--fresh-gateway moves your OpenClaw state aside and onboards fresh; add --accept-risk to confirm"
fi

if [ "$FRESH" = "1" ] && [ "$MODE" = "apply" ]; then
  aside="$HOME/.openclaw.pre-clean-$(date +%Y%m%d)"
  [ -e "$aside" ] && die "$aside already exists; move it aside first"
fi

NODE_BIN="$NVM_HOME/versions/node/v$NODE_VER/bin"
DRIFT=0

pinned_openclaw() {
  python3 - "$HOME" "$TARBALL" <<'PY' 2>/dev/null || true
import json, sys, tarfile
home, tarball = sys.argv[1], sys.argv[2]
if tarball:
    try:
        with tarfile.open(tarball, "r:*") as tf:
            member = tf.extractfile("package/package.json")
            if member:
                data = json.load(member)
                pin = data.get("dependencies", {}).get("openclaw")
                if pin:
                    print(pin)
                    sys.exit(0)
    except Exception:
        pass
for name in ("@diazmelgarejo/alphaclaw", "@chrysb/alphaclaw"):
    try:
        data = json.load(open(f"{home}/.alphaclaw/node_modules/{name}/package.json"))
    except (OSError, ValueError):
        continue
    pin = data.get("dependencies", {}).get("openclaw")
    if pin:
        print(pin)
        break
PY
}
[ -n "$OPENCLAW_VER" ] || OPENCLAW_VER="$(pinned_openclaw)"
[ -n "$OPENCLAW_VER" ] || OPENCLAW_VER="$DEFAULT_OPENCLAW"

heading() { printf '== %s\n' "$*"; }
drift() { DRIFT=1; printf 'DRIFT %s\n' "$*"; }
ok() { printf 'OK    %s\n' "$*"; }

# do_cmd: print the command; run it only in --apply. In --check nothing is printed or run.
do_cmd() {
  case "$MODE" in
    plan) printf '  $ %s\n' "$*" ;;
    apply) printf '  $ %s\n' "$*"; "$@" ;;
  esac
}
# nvm_cmd and node_cmd show the command as a person would type it; apply runs it with nvm sourced / node on PATH.
nvm_cmd() {
  case "$MODE" in
    plan) printf '  $ %s\n' "$*" ;;
    apply) printf '  $ %s\n' "$*"; bash -c ". \"$NVM_HOME/nvm.sh\" && $*" ;;
  esac
}
node_cmd() {
  case "$MODE" in
    plan) printf '  $ %s\n' "$*" ;;
    apply) printf '  $ %s\n' "$*"; env PATH="$NODE_BIN:$PATH" "$@" ;;
  esac
}

step_node() {
  heading "1 node $NODE_VER (nvm default)"
  if [ "$MODE" = "check" ]; then
    if [ -x "$NODE_BIN/node" ]; then ok "node v$NODE_VER installed"; else drift "node v$NODE_VER is not installed under $NVM_HOME"; fi
    if grep -q "$NODE_VER" "$NVM_HOME/alias/default" 2>/dev/null; then ok "nvm default is $NODE_VER"; else drift "nvm default is not $NODE_VER"; fi
    return 0
  fi
  if [ -n "$MIGRATE_FROM" ]; then
    nvm_cmd "nvm install $NODE_VER --reinstall-packages-from=$MIGRATE_FROM"
  else
    nvm_cmd "nvm install $NODE_VER"
  fi
  nvm_cmd "nvm alias default $NODE_VER"
  echo "  note: npm 11 skips package install scripts; run each migrated global CLI afterwards and rebuild natives that fail"
}

step_openclaw() {
  heading "2 openclaw $OPENCLAW_VER (global, under node $NODE_VER)"
  if [ "$MODE" = "check" ]; then
    have="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$NODE_BIN/../lib/node_modules/openclaw/package.json" 2>/dev/null || true)"
    if [ "$have" = "$OPENCLAW_VER" ]; then ok "openclaw $have"; else drift "global openclaw is '${have:-absent}', expected $OPENCLAW_VER"; fi
    return 0
  fi
  node_cmd npm install -g "openclaw@$OPENCLAW_VER"
}

step_alphaclaw() {
  heading "3 alphaclaw fork build (PR 34) in ~/.alphaclaw"
  if [ "$MODE" = "check" ]; then
    if [ -f "$HOME/.alphaclaw/node_modules/@diazmelgarejo/alphaclaw/package.json" ]; then ok "@diazmelgarejo/alphaclaw installed"; else drift "the fork build is not installed in ~/.alphaclaw"; fi
    return 0
  fi
  if [ -z "$TARBALL" ]; then
    echo "  skipped: pass --alphaclaw-tarball (build it in the AlphaClaw worktree with: pnpm install --frozen-lockfile && npm pack)"
    return 0
  fi
  do_cmd mkdir -p "$HOME/.alphaclaw/vendor"
  do_cmd cp "$TARBALL" "$HOME/.alphaclaw/vendor/"
  node_cmd npm install --prefix "$HOME/.alphaclaw" "$HOME/.alphaclaw/vendor/$(basename "$TARBALL")"
  node_cmd npm uninstall --prefix "$HOME/.alphaclaw" @chrysb/alphaclaw
  if [ "$EXPLICIT_OPENCLAW" = "0" ]; then
    local new_pin
    new_pin="$(pinned_openclaw)"
    if [ -n "$new_pin" ] && [ "$new_pin" != "$OPENCLAW_VER" ]; then
      OPENCLAW_VER="$new_pin"
      node_cmd npm install -g "openclaw@$OPENCLAW_VER"
    fi
  fi
}

step_link() {
  heading "4 stable node link and launch agent"
  if [ "$MODE" = "check" ]; then
    if out="$(PYTHONPATH="$PT_ROOT/src" python3 -m perpetua_tools.openclaw_runtime --check 2>&1)"; then ok "service uses the stable link"; else drift "runtime link"; printf '%s\n' "$out"; fi
    return 0
  fi
  do_cmd env "PYTHONPATH=$PT_ROOT/src" python3 -m perpetua_tools.openclaw_runtime --apply
  return 0
}

step_gateway() {
  [ "$FRESH" = "1" ] || return 0
  heading "5 fresh gateway state (opt-in; the old state is renamed, never deleted)"
  local aside="$HOME/.openclaw.pre-clean-$(date +%Y%m%d)"
  [ -e "$aside" ] && [ "$MODE" = "apply" ] && die "$aside already exists; move it aside first"
  do_cmd launchctl bootout "gui/$(id -u)/ai.openclaw.gateway" || true
  if [ -e "$HOME/.openclaw" ]; then
    do_cmd mv "$HOME/.openclaw" "$aside"
  elif [ "$MODE" = "plan" ]; then
    printf '  $ mv %s %s (if present)\n' "$HOME/.openclaw" "$aside"
  fi
  node_cmd openclaw onboard --non-interactive --accept-risk --flow quickstart --mode local \
    --gateway-bind loopback --gateway-port "$PORT" --gateway-auth token --auth-choice skip \
    --skip-channels --skip-skills --skip-search --skip-hooks --install-daemon
  step_link
  echo "  next: restore state in baby steps (see the header), one gateway check after each"
}

step_node
step_openclaw
step_alphaclaw
if [ "$FRESH" != "1" ]; then
  step_link
fi
step_gateway

if [ "$MODE" = "check" ]; then
  [ "$DRIFT" = "0" ] && echo "OK: runtime matches the 2026-11-25 baseline" || echo "DRIFT: run with --plan to see the fix, then --apply"
  exit "$DRIFT"
fi
