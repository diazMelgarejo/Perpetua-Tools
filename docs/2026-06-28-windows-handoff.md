# Windows → Mac Handoff — 2026-06-28

> **Windows:** Phase 6+9 ✅ pushed to `main`. Canaries green.  
> **Mac:** Cross-harness E2E + T5 tags remain.  
> **Canonical Mac checklist:** [orama-system `2026-06-28-mac-e2e-handoff.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-28-mac-e2e-handoff.md)

## What Windows completed (on `main`)

- ✅ Hermes Phase 6+9: thin wrappers + `install_hermes_thin_skills.py --verify`
- ✅ `verify_partner_canaries.py`: LM Studio + Hermes + Codex + cursor-agent PASS
- ✅ `ensure-partner-cli-paths.ps1` + parametric partner CLI paths
- ✅ `codex-cli-v142-dispatch.md` canonical card + `dispatch_codex_partner.py`
- ✅ OpenClaw optional on Windows (`start.ps1` skips when no `openclaw.json`)
- ✅ **`start.ps1` rehab (`2717eee`):** bash-style flags, `$listenerPid`, uvicorn paths, `ContainsKey` — live verify 8000/8001/8002 UP
- ✅ Canary model `stepfun/step-3.7-flash:free`; LM Studio `state=loaded` probe
- ✅ PT memory: `CODEX_V142_DISPATCH_2026-06-28.md`, `lesson_2cef6113c1f1`

## LAN peer (Mac ↔ Win — same instructions both hosts)

**Canonical playbook:** [orama `lan-peer-self-talk.md` § Operator playbook](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/hermes-harness/references/lan-peer-self-talk.md#operator-playbook)

- Hermes: `/lan-peer-self-talk`
- Win start: `.\platform\windows\start.ps1 --lan-peer`
- Mac start: `./start.sh --lan-peer --no-open`

## Mac operator — start here

```bash
# 1. Sync
cd ~/code/OpenClaw/orama-system && git pull --ff-only origin main
cd ~/code/OpenClaw/Perpetua-Tools && git pull --ff-only origin main

# 2. Mac-local E2E
cd ~/code/OpenClaw/orama-system
bash start.sh --status
bash scripts/check-local-env.sh
bash start.sh --hardware-policy

# 3. Keychain (user action)
printf '%s' 'YOUR_GATEWAY_AUTH_TOKEN' | \
  bash scripts/openclaw/store_keychain_secret.sh openclaw.gateway-auth-token
source scripts/openclaw/load_keychain_secrets.sh

# 4. Cross-harness (Win LM Studio must be on LAN)
WIN_IP=$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path.home().joinpath('.openclaw/state/last_discovery.json').read_text())['endpoints']['win']['ip'])")
curl -sS "http://${WIN_IP}:1234/v1/models" | head
bash start.sh --hardware-policy

# 5. T5 tags (after cross-harness green)
git tag v1.1.1 -m "v1.1.1 — security hardening + fail-closed routing"
git push --tags origin
```

## Win ↔ Mac IP invariant

**Never hardcode** the Windows IP. Read from discovery:

```bash
python3 -c "import json,pathlib; print(json.loads(pathlib.Path.home().joinpath('.openclaw/state/last_discovery.json').read_text())['endpoints']['win']['ip'])"
```

Discovery: `$PERPETUA_TOOLS_PATH/scripts/discover-lm-studio.sh`

## Windows regression check (only if needed)

```powershell
.\platform\windows\ensure-partner-cli-paths.ps1
python bin\orama-system\skills\hermes-harness\scripts\verify_partner_canaries.py
.\platform\windows\start.ps1 --hardware-policy
```

## Still blocked on Mac

| Item | Owner |
|------|-------|
| `openclaw.gateway-auth-token` Keychain | Mac user |
| Mac→Win LM Studio LAN probe | Mac |
| Cross-harness `--hardware-policy` | Mac |
| T5 git tags `v1.1.1` / `v1.0.0` | Mac after E2E green |
