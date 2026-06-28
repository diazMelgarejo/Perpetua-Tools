# Windows Handoff Instructions — 2026-06-28

> **Context:** Mac E2E complete. These tasks require the Windows machine (RTX 3080 LM Studio).

## Prerequisites (Windows side)

1. LM Studio running with the correct model loaded (`qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2`)
2. `LM_STUDIO_WIN_ENDPOINTS=http://192.168.254.100:1234` reachable from Mac LAN
3. OpenClaw clone at `C:\OpenClaw\` or equivalent

## Pending Windows tasks

### T5: Git tag release (blocked on Win E2E green)

```bash
# After Win E2E passes:
git tag v1.1.1 -m "v1.1.1 — security hardening + fail-closed routing"
git tag v1.0.0 -m "v1.0.0 — baseline stable"
git push --tags origin
```

### LM Studio LAN probes

```powershell
# On Windows: verify LM Studio is serving on LAN
netstat -an | Select-String ":1234"
# Confirm the Win IP matches ~/.openclaw/state/last_discovery.json endpoints.win.ip
```

### Hermes Phase 6+9 (when Win coder is back online)

Phase 6: `scripts/hermes/phase6-win-validation.sh` (LAN routing validation)  
Phase 9: `scripts/hermes/phase9-full-harness.sh` (full cross-harness hardware affinity)

### Cross-harness hardware affinity verification

Run from Mac (after Win LM Studio is online):

```bash
bash ~/code/OpenClaw/orama-system/scripts/start.sh --hardware-policy
# Expected: Win node routes qwen3.5-27b-..., Mac routes qwen3.5:9b-nvfp4 + qwen3.5-9b-mlx
```

## Keychain secrets still needed on Mac

The following secrets must be provided by the user and stored via `store_keychain_secret.sh`:

```bash
# TELEGRAM_BOT_TOKEN — get from @BotFather or existing .env on Win
printf '%s' 'YOUR_TELEGRAM_BOT_TOKEN' | \
  bash ~/code/OpenClaw/orama-system/scripts/openclaw/store_keychain_secret.sh openclaw.telegram-bot-token

# GATEWAY_AUTH_TOKEN — get from PT gateway config or Win secrets store
printf '%s' 'YOUR_GATEWAY_AUTH_TOKEN' | \
  bash ~/code/OpenClaw/orama-system/scripts/openclaw/store_keychain_secret.sh openclaw.gateway-auth-token
```

Once stored, `source ~/code/OpenClaw/orama-system/scripts/openclaw/load_keychain_secrets.sh` exports all four OPENCLAW_* vars.

## Win ↔ Mac IP invariant

**Never hardcode** the Windows IP. Always read from:
```bash
cat ~/.openclaw/state/last_discovery.json | python3 -c "import sys,json; print(json.load(sys.stdin)['endpoints']['win']['ip'])"
```

The launchd watcher (`com.orama.network-watch`) refreshes this every 30s.  
Discovery script: `Perpetua-Tools/scripts/discover-lm-studio.sh`

