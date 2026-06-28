# Windows Handoff Instructions — 2026-06-28

> **Context:** Mac E2E complete. Windows Hermes testdrive **partial green** 2026-06-28.

## Prerequisites (Windows side)

1. LM Studio running with the correct model loaded (`qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2`)
2. `LM_STUDIO_WIN_ENDPOINTS` reachable from Mac LAN (read Win IP from discovery — never hardcode)
3. OpenClaw **optional** on Windows — Hermes is the primary orchestrator

## Completed on Windows (2026-06-28)

- ✅ Hermes Phase 6: `install_hermes_thin_skills.py --install --verify --test`
- ✅ Hermes Phase 9: four thin wrappers installed under `%LOCALAPPDATA%\hermes\skills\pt-orama\`
- ✅ `verify_partner_canaries.py`: LM Studio + Hermes + Codex + cursor-agent PASS
- ✅ `start.ps1 --hardware-policy`: PT `--list` + Win model `--validate` (skips `--check-openclaw` when no `openclaw.json`)
- ✅ Partner CLI PATH: `platform/windows/ensure-partner-cli-paths.ps1`

## Pending (needs Mac + Win pair)

### T5: Git tag release (blocked on Mac↔Win cross-harness E2E)

```bash
# After Mac LAN probe + cross-harness affinity green:
git tag v1.1.1 -m "v1.1.1 — security hardening + fail-closed routing"
git tag v1.0.0 -m "v1.0.0 — baseline stable"
git push --tags origin
```

### LM Studio LAN probes

```powershell
# On Windows: verify LM Studio is serving on LAN
netstat -an | Select-String ":1234"
```

From Mac (never hardcode Win IP):

```bash
WIN_IP=$(python3 -c "import json,pathlib; p=pathlib.Path.home()/'.openclaw/state/last_discovery.json'; print(json.loads(p.read_text())['endpoints']['win']['ip'])")
curl -s "http://${WIN_IP}:1234/v1/models" | head
```

### Cross-harness hardware affinity verification

Run from Mac when Win LM Studio is online:

```bash
bash ~/code/OpenClaw/orama-system/scripts/start.sh --hardware-policy
```

## Keychain secrets still needed on Mac

```bash
# GATEWAY_AUTH_TOKEN — user must provide
printf '%s' 'YOUR_GATEWAY_AUTH_TOKEN' | \
  bash ~/code/OpenClaw/orama-system/scripts/openclaw/store_keychain_secret.sh openclaw.gateway-auth-token
```

Once stored, `source ~/code/OpenClaw/orama-system/scripts/openclaw/load_keychain_secrets.sh` exports all four OPENCLAW_* vars.

## Win ↔ Mac IP invariant

**Never hardcode** the Windows IP. Always read from:

```bash
python3 -c "import json,pathlib; print(json.loads(pathlib.Path.home().joinpath('.openclaw/state/last_discovery.json').read_text())['endpoints']['win']['ip'])"
```

Discovery script: `$PERPETUA_TOOLS_PATH/scripts/discover-lm-studio.sh`
