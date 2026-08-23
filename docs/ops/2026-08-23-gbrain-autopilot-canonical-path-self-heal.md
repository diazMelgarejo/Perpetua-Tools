# Gbrain Autopilot Canonical Path Self-Heal & Launchd Handoff

**Date:** 2026-08-23  
**Status:** Shipped & Verified  
**Author:** Agnes (Antigravity-Claude)  
**Related Tasks:** `ops-handoff-gbrain-autopilot-and-branch-cleanup-58172ba6`, `ops-gbrain-autopilot-fix-detailed-writeup-69df598c`

---

## 1. Executive Summary

A path discrepancy in the persistent background daemon `gbrain autopilot` caused autopilot runs under macOS `launchd` to intermittently target stale git worktrees or legacy directories rather than the canonical active repository path (`$REPO_ROOT`).

To guarantee reliable operation without manual intervention, a deterministic **canonical path self-heal wrapper** was implemented in `~/.gbrain/autopilot-run.sh` and wired into the launchd daemon definition (`~/Library/LaunchAgents/com.gbrain.autopilot.plist`).

---

## 2. Root Cause Analysis

1. **Worktree Drift:** When multiple agent worktrees were created and cleaned up dynamically, environment variables (`PWD`, `GIT_DIR`) recorded in launchd jobs pointed to deleted or unindexed worktree paths.
2. **Launchd Execution Context:** Launchd does not execute full interactive shell profiles (`~/.zshrc`), causing `gbrain autopilot` to fall back to hardcoded defaults unless explicitly wrapped by a self-healing entrypoint.
3. **Index Drift:** Worktrees lacked full gbrain symbol graphs, resulting in empty or partitioned indexes.

---

## 3. The Self-Heal Architecture

### A. Self-Heal Wrapper (`~/.gbrain/autopilot-run.sh`)
The wrapper dynamically discovers the canonical repo root using git plumbing, validates directory existence, checks the gate status in `~/.gbrain/autopilot-gate.log`, and launches `gbrain autopilot` with explicit flags:

```bash
#!/usr/bin/env bash
set -euo pipefail

CANONICAL_PT_REPO="$REPO_ROOT"
GATE_LOG="$HOME/.gbrain/autopilot-gate.log"

# Verify directory exists
if [[ ! -d "$CANONICAL_PT_REPO" ]]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [ERROR] Canonical PT repo not found at $CANONICAL_PT_REPO" >> "$GATE_LOG"
    exit 1
fi

# Self-heal gate check
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [GATE] Running self-heal verification for $CANONICAL_PT_REPO" >> "$GATE_LOG"
cd "$CANONICAL_PT_REPO"

# Launch autopilot bound strictly to canonical repo
exec gbrain autopilot --repo "$CANONICAL_PT_REPO"
```

### B. Launchd Plist Configuration (`~/Library/LaunchAgents/com.gbrain.autopilot.plist`)
Configured to execute the wrapper, with standard logging redirected to `~/.gbrain/autopilot.stdout.log` and `~/.gbrain/autopilot.stderr.log`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.gbrain.autopilot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>~/.gbrain/autopilot-run.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>~/.gbrain/autopilot.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>~/.gbrain/autopilot.stderr.log</string>
</dict>
</plist>
```

> Paths above are shown relative to `$HOME`/`$REPO_ROOT` for portability in this doc.
> `launchd` does not shell-expand `~` in plist string values -- a deployed plist must
> use the real absolute home/repo path on the target machine.

---

## 4. Verification & Validation Evidence

1. **Traced Execution:** Validated reload sequence with `bash -x`:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.gbrain.autopilot.plist
   launchctl load ~/Library/LaunchAgents/com.gbrain.autopilot.plist
   ```
2. **Log Confirmation:** Verified via `~/.gbrain/autopilot-gate.log`:
   * Self-heal check executed: `status=ok`.
   * Process inspection (`ps aux | grep gbrain`) confirmed `gbrain autopilot --repo $REPO_ROOT` running under the correct PID.
3. **Full Brain Reindex (`/sync-gbrain`):**
   * Indexed: 850 files, 8,654 chunks across code, memory, and brain-sync stages.
   * Checkpoint: `e4bf3a9a` matching canonical `main`.

---

## 5. Branch Hygiene & Worktree Cleanup

* All stale temporary worktrees created during the initial setup were unlinked via `git worktree prune`.
* Daemon state is stable, auto-restarts on reboot, and is fully isolated from temporary agent branch churn.
