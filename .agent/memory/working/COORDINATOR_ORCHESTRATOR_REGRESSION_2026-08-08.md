# Arc: The Coordinator→Orchestrator Regression (A Rejected Suggestion Came Back)

**Date:** 2026-08-08
**Repos:** orama-system (where it happened + where it was fixed); PT (where the
governing rule's lockstep copy lives, verified unaffected)
**Severity:** Low functional impact (identity/naming fields, not runtime logic),
high process significance — this is the first confirmed case this session of an
automated fix pass **reverting a deliberate, reasoned decision from an earlier
session with zero awareness that decision existed.**

## The bug shape

An automated CodeRabbit-fix pass, running unattended mid-session on
orama-system PR #290, re-applied a code-review suggestion that a **different,
earlier session had already seen and explicitly rejected** — because the
automated pass had no way to know that history existed. The rejection lived
only in a commit message and a doc's prose; nothing in the actual file content
being edited carried a machine-checkable "don't do this" signal.

## Timeline (chronological, both repos)

| When | Repo | Commit(s) | What it did | Right/Wrong |
|---|---|---|---|---|
| 2026-08-06 20:32 | orama-system | [`ca66d944`](https://github.com/diazMelgarejo/orama-system/commit/ca66d9448c2da93fd5a3eda32691c88ab9eb78a4) / `a889d570` / `087899dd` (rewrite-duplicate SHAs, identical content) | **Explicitly rejected** CodeRabbit review 4873990444's suggestion to rename relay-cursor's `coordinator` identity to `orchestrator`. Scoped the ban itself instead: bans "coordinator" as orchestrator's synonym in the control-plane; exempts a documented, distinct persona (relay-cursor is the worked example) | ✅ **Right** |
| 2026-08-06 20:33 | Perpetua-Tools | [`75187d71`](https://github.com/diazMelgarejo/Perpetua-Tools/commit/75187d71005cf6c78327023bd0c205647519d240) | Lockstep copy of the same carve-out in PT's `CLAUDE.md` | ✅ **Right** |
| 2026-08-08 05:19 | orama-system | [`e2bc041c`](https://github.com/diazMelgarejo/orama-system/commit/e2bc041c7271fed535b2a5e3705d1803ae6d9812) / `6c38ac11` (rewrite-duplicate SHAs, identical content) | Automated CodeRabbit-fix pass on PR #290, re-applying review 4873990444's *original* suggestion — renamed `adapter.cursor-coordinator` → `adapter.cursor-orchestrator` and "Coordinator & Cross-Repo Relay" → "Orchestrator & Cross-Repo Relay" across `REGISTRY.yml`, `personas/relay-cursor.yaml`, `relay-cursor/SOUL.md`, `relay-cursor/agent.md` | ❌ **Wrong** — reverts `ca66d944` with zero memory of it |
| 2026-08-08 (later, same session) | orama-system | `083df707` | A *different* dispatched fix (narrowing relay-cursor's `allowed-tools` to match its real capabilities) touched the same 4 files but for capability lists only — inherited the already-wrong naming without noticing it | ⚠️ Not itself wrong, but a missed catch during a regression sweep that specifically checked these files for *other* things |
| 2026-08-08 (human-caught) | orama-system | — | User asked directly: "is this for real? ... we made it very clear not to confuse the two" | 🔍 **Caught** — not by any script, by a human re-reading the diff |
| 2026-08-08 | orama-system | `fc7a4efc` | Reverted all 4 files back to `adapter.cursor-coordinator` / "Coordinator & Cross-Repo Relay" | ✅ **Fixed** |
| 2026-08-08 | orama-system | (pending, PR #290 branch) | Strengthened `docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md` §1/§2 with an incident callout + a new "exemption-integrity" check (see below); added a dedicated section to `AGENTS.md` (previously had **zero** mention of this rule); made the pointer in `CLAUDE.md`'s navigation table louder | 🛡️ **Hardened** |
| 2026-08-08 | Perpetua-Tools | this file, on `2026-08-08-001-pt-orama-discovery-and-retrospective` (not pushed) | This working-memory record | 📝 **Recorded** |

## Why the guardrail didn't catch it (the actual root cause, not just "an agent made a mistake")

`docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md` §2 already had a documented bash
detection sweep for exactly this class of problem — a negative grep for
`Coordinator|coordinator` outside an explicit allowlist, plus a positive check
that `orchestrator` terminology still exists somewhere. Two structural gaps
meant it never had a chance:

1. **It was never wired into CI.** The doc explicitly says *"Detection sweep,
   not yet a passing acceptance criterion... Do not gate CI on this
   command."* It's a documented intent, not an enforced check. No workflow
   file runs it.
2. **Even as documentation, the check had a blind spot.** The negative grep
   proves "coordinator" doesn't leak *outside* the relay-cursor allowlist. It
   says nothing about whether the *allowlisted* files still correctly say
   "coordinator" — so an agent silently reverting the exemption *inside* its
   own allowed zone would pass both the negative and positive checks with
   zero signal, precisely because it looks like compliance with the
   orchestrator-only rule from the outside.

Fixed in the same PR #290 push: added a third check that verifies each
allowlisted file still contains "coordinator" — i.e., proves the exemption is
actually being *used*, not just that the ban isn't leaking elsewhere.

## The deeper pattern (why this is worth a working-memory entry, not just a commit message)

This is the same failure shape as
[[feedback_verify_before_replaying_past_agent_work]] and this session's own
PR #283 case study (`orama-system/docs/LESSONS.md` §2026-08-08, "ALWAYS
verify, NEVER trust") — but one layer removed: that lesson was about verifying
a *merge* actually landed what a branch intended. This one is about verifying
an *automated fix* isn't re-litigating a *decision*, not just a diff.
CodeRabbit (or any stateless review bot) has no persistent memory across
sessions — it will keep suggesting the same "fix" every time it sees the
pattern, because from its perspective nothing has changed since the last time
it suggested it. The carve-out reasoning lived in a commit message and prose,
readable by a human doing a careful diff review, invisible to an automated
pass applying suggestions mechanically.

**The generalizable rule:** any doc that documents *rejecting* an automated
tool's suggestion needs the rejection reasoning re-discoverable from the
*code itself* (a comment, a checked-in test, a wired CI gate), not only from
history — because the same suggestion will resurface, and the thing that
resurfaces it won't read `git log`.

## What actually got fixed, file by file (orama-system)

- `bin/agents/REGISTRY.yml` — `soul_id`, `stage`, `notes` reverted to coordinator
- `bin/agents/personas/relay-cursor.yaml` — `soul_id`, `role` reverted
- `bin/agents/relay-cursor/SOUL.md` — `soul_id`, opening description reverted
- `bin/agents/relay-cursor/agent.md` — `description`, opening line reverted
- `docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md` §1 — incident callout added to
  the scope note; §2 — exemption-integrity check added to the detection sweep
- `AGENTS.md` — new section, previously absent entirely
- `CLAUDE.md` — navigation table row made louder (points at the incident, not
  just the abstract rule)

## Cross-references

- `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md` — this session's other
  "trust the artifact, not the report" incidents (PR #283, the CodeQL
  re-flags on `lan_peer_files.py`).
- orama-system `docs/LESSONS.md` §2026-08-08 ("ALWAYS verify, NEVER trust") —
  the sibling incident this same session, same root failure shape.
- orama-system `docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md` §1 — the
  authoritative rule text and now this incident's permanent callout.
- orama-system PR: <https://github.com/diazMelgarejo/orama-system/pull/290>
