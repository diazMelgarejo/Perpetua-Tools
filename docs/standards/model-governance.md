# Model governance (Perpetua-Tools pin)

Canonical standard (cite, do not copy):
[Alexandria model-governance](https://github.com/oramasys/alexandria/blob/docs/mig-pack-ingest-20260925/docs/standards/model-governance.md)
([PR #1](https://github.com/oramasys/alexandria/pull/1), tip `d6da6781`).

Sister pin (same model ids):
[orama-system PR #381](https://github.com/diazMelgarejo/orama-system/pull/381)
(head `812147f7`).

This repo keeps a machine-readable pin at
[`config/model-governance.yml`](../../config/model-governance.yml)
and a fail-closed checker at
[`src/perpetua_tools/model_governance.py`](../../src/perpetua_tools/model_governance.py).
Plans and reviews link the Alexandria file.
They do not restate model ids.

## Relationship to existing Perpetua-Tools routing policy

This pin **supplements** Perpetua-Tools' existing routing policy; it does not
replace it. The Alexandria standard is still 🟡 Proposed.

- The primary routing logic stays where it was: the selection order in
  [`SKILL.md`](../../SKILL.md) (`orchestrator/model_registry.py` with
  `config/models.yml` and `routing.yml`) and the tier heuristic in
  [`.cursor/commands/model-route.md`](../../.cursor/commands/model-route.md).
- This pin adds two things: the **fallback** used when that logic cannot decide
  from verifiable criteria (the harness default or an allowed alternative, never
  a self-escalation), and **alternate paths** for harnesses other than Claude Code.
- **Escalation to Opus or Fable:** see
  [Escalation approval regimes](#escalation-approval-regimes). This is the one
  place the rule is stated; the other files link here and do not restate it.
- Outdated model ids in the existing policy are refreshed in place. The policy
  text around them is not rewritten.

## Escalation approval regimes

Operator ruling, 2026-10-24. A proof cannot be demanded where nothing can issue
or verify it, so the approval needed depends on whether the **escalation grant
mechanism** exists. The mechanism exists only when both hold, and both are
checkable in this repo:

1. `assert_launch_allowed` has a production caller at the launch boundary
   (today `grep` finds none outside `model_governance.py`).
2. The control plane verifies the S-AuthZ bearer and the signed HITL approval
   (the proof defined under "Escalation token" below).

| Regime | When | What approves Opus or Fable |
| --- | --- | --- |
| 1, interim | Either condition is unmet (**current state**) | An operator `AskUserQuestion` confirmation, as the existing tiering says. Record the model, effort, task and, for Fable, the budget cap on the PR or issue. This is a human decision, not a token, and an agent never supplies it for itself. |
| 2, enforced | Both conditions are met | The escalation token below, verified by the control plane. An `AskUserQuestion` confirmation alone no longer approves. |

The switch is a change in the repo (a production caller and a verifier), not a
config flag, environment variable or note, so it cannot be flipped by an agent.
Alexandria records the same two regimes in its
[Escalation approval regimes](https://github.com/oramasys/alexandria/blob/docs/mig-pack-ingest-20260925/docs/standards/model-governance.md#escalation-approval-regimes)
section (tip `d6da6781`), so its "Until enforcement lands" rule now points at
Regime 1 instead of requiring a proof reference.

## What Perpetua-Tools must follow

- The **harness** chooses the path. There is no Claude-only
  (or any single-provider-only) routing default for agents.
- **Cursor / Grok Bot:** default launch is `grok-4.7` at
  `{effort: medium, fast: false}`
  (usage label `cursor-grok-4.7-medium`).
  `composer-2.5` and `gpt-5.6-terra` (medium) are allowed with fast off,
  as explicit operator picks.
  `grok-4.5` and superseded `grok-4.6` are banned.
  `auto` / `default` is editor-only, never for agents.
- **Anthropic:** default is `claude-sonnet-5-5` at medium
  (`claude-sonnet-5` is a legacy pin only).
  Planning Opus permits medium/high with harness classification. Non-planning
  Opus needs a per-use approval, with medium as its approval candidate default;
  explicit approved high remains permitted. Fable needs approval and a budget cap.
- **Effort ceiling (operator ruling 10):** `xhigh` and `max` are refused on
  every harness path, including when matching approval metadata is supplied.
  The check applies to both effort fields before path-specific policy runs.
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

## Claude Code model allowlist (managed settings)

The managed-settings template and the required-deployment rule live in the
orama-system pin, which this repo mirrors:
[Claude Code model allowlist (managed settings)](https://github.com/diazMelgarejo/orama-system/blob/main/docs/standards/model-governance.md#claude-code-model-allowlist-managed-settings).
`assert_launch_allowed` has no production caller here yet either, so the same
rule applies: an environment that has not deployed that template at the managed
boundary is not a supported environment for agent work.
