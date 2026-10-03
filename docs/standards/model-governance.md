# Model governance (Perpetua-Tools pin)

Canonical standard (cite, do not copy):
[Alexandria model-governance](https://github.com/oramasys/alexandria/blob/docs/mig-pack-ingest-20260925/docs/standards/model-governance.md)
([PR #1](https://github.com/oramasys/alexandria/pull/1), tip `e7ee9db6`).

Sister pin (same model ids):
[orama-system PR #381](https://github.com/diazMelgarejo/orama-system/pull/381)
(head `812147f7`).

This repo keeps a machine-readable pin at
[`config/model-governance.yml`](../../config/model-governance.yml)
and a fail-closed checker at
[`src/perpetua_tools/model_governance.py`](../../src/perpetua_tools/model_governance.py).
Plans and reviews link the Alexandria file.
They do not restate model ids.

## What Perpetua-Tools must follow

- The **harness** chooses the path. There is no Claude-only
  (or any single-provider-only) routing default for agents.
- **Cursor / Grok Bot:** default launch is `grok-4.6` at
  `{effort: medium, fast: false}`
  (usage label `cursor-grok-4.6-medium`).
  `composer-2.5` is allowed with fast off.
  `grok-4.7` needs an escalation token and still runs medium / fast off.
  `grok-4.5` is banned.
  `auto` / `default` is editor-only, never for agents.
- **Anthropic:** default is `claude-sonnet-5-5` at medium
  (`claude-sonnet-5` is a legacy pin only).
  `claude-opus-5-5` (high) and `claude-fable-5-1` each need an
  escalation token; Fable also needs a hard budget cap.
- **Escalation token** means a proven control-plane (S-AuthZ) bearer
  **and** a fresh signed HITL approval (GitHub Verified signature on
  device, offline GPG/PGP, or an online signer tied to the control
  plane), expiring in at most 24h.
  Config flags, env vars, agent-writable files, and cached approvals
  are not proof.
- This pin does **not** reorder the runtime frugality ladder
  (local tiers first, paid last).
  Cost gate stays **fail-closed**.
  Cloud escalation stays **default-deny**.
