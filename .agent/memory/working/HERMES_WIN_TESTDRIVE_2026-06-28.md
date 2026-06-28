# Hermes Windows Testdrive — 2026-06-28

## Gold nuggets

1. **LM Studio single-model invariant** — one loaded model per instance; second load fails (`Operation canceled`). Use `/api/v0/models` `state=loaded` for canaries; logs at `%USERPROFILE%\.lmstudio\server-logs`.
2. **Partner CLI PATH** — `platform/windows/ensure-partner-cli-paths.ps1` idempotently adds Hermes, Codex, AGY, cursor-agent dirs to User PATH.
3. **Hermes canary model** — `stepfun/step-3.7-flash:free` via Nous (replaces retired `nemotron-3-ultra:free`).
4. **Windows OpenClaw optional** — Hermes-only hosts skip `openclaw.json` and `--check-openclaw`; optional when file exists.
5. **cursor-agent Windows path** — `%LOCALAPPDATA%\cursor-agent` (not `Programs\cursor-agent`).
6. **Python subprocess on Win** — resolve `.cmd`/`.ps1` shims via `_resolve_partner_cli` + `_run_partner` in `verify_partner_canaries.py`.

## Evidence

- `verify_partner_canaries.py`: LM Studio, Hermes, Codex, cursor-agent PASS; AGY UNAVAILABLE (timeout)
- 15+ pytest in `test_verify_partner_canaries.py`
- Thin wrappers: council, review, delegate, pt-hardware-policy
