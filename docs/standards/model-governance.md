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
- **Cursor / Grok Bot:** default launch is `grok-4.7` at
  `{effort: medium, fast: false}`
  (usage label `cursor-grok-4.7-medium`).
  `composer-2.5` is allowed with fast off.
  `grok-4.6`, `grok-4.5`, and `gpt-6-astra` are banned launch IDs.
  `auto` / `default` is editor-only, never for agents.
- **Anthropic:** default is `claude-sonnet-5-5` at medium
  (`claude-sonnet-5` is a legacy pin only).
  Planning Opus permits medium/high with harness classification. Non-planning
  Opus needs a per-use approval, with medium as its approval candidate default;
  explicit approved high remains permitted. Fable needs approval and a budget cap.
- **Effort ceiling:** `xhigh` and `max` are refused on every harness path,
  including when matching approval metadata is supplied. Both effort fields
  are checked before path-specific policy runs.
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

## Role selection contract

`plan_launch` returns the requested launch, the immediately permitted launch,
an approval candidate and a reason. It accepts a harness-supplied task kind;
agents must not supply that classification through their own payloads.
Planning permits Opus at medium/high and Sol at medium. Non-planning requests
fall back immediately to Sonnet/Terra medium while human approval is pending.
Haiku/Luna controller rows and the Gemini medium default are explicit pins.
Ultracode always requires a human decision and otherwise selects standard mode.

The result contains policy facts only. Before executing a gated candidate,
the caller must obtain and consume authenticated Phylax authority and establish
the durable execution lease. Neither `LaunchPlan` nor `EscalationProof` proves
that those steps happened. `assert_launch_allowed` checks the requested policy
tuple; it does not silently execute a returned fallback or verify signatures.
