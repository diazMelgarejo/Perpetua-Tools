# Arc: PT/orama Synergy Plan — the Method, Not the Plan Itself

**Date:** 2026-08-07 → 2026-08-08
**Parent essay:** `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md`
**Artifact:** the actual plan lives in orama-system at
`$ORAMA_SYSTEM_PATH/docs/plans/2026-08-07-pt-orama-minimal-synergy-plan.md`
(resolve with `scripts/resolve_orama_root.sh` if the env var isn't set —
see that script for the full discovery fallback chain) — this essay is
about *how* it got made, so the method survives independently of that one
document.

## The shape of the method (reusable beyond this one plan)

1. One agent (`agy`) produced a first-pass research brief — existing-
   synergy claims and friction claims, scoped to navigation files
   (`CLAUDE.md`/`AGENTS.md`).
2. Two *different* agents (codex, cursor-agent) independently critiqued
   that brief adversarially — each reading the actual cited files on
   disk, not trusting the brief's prose, and **not shown each other's
   output** before writing their own critique.
3. A human/lead-agent synthesis pass read both critiques, found the points
   where they disagreed with *each other* (not just with the brief), and
   resolved each by re-reading the disputed file personally rather than
   picking a side by vote or averaging severities.

Step 3 is the part worth remembering distinctly: with two independent
adversarial reviews in hand, the temptation is to treat agreement as
truth and disagreement as noise to smooth over. Every disagreement found
here was actually resolvable — not a case of "reasonable people differ,"
but a case of "one of them didn't check a specific fact the other did."

## The three real disagreements, and what settled each

- **Is `ORAMASYS-MASTERY-v3.md` canonical?** The brief implied yes. Codex
  said no (it's a labeled "Review draft"). Cursor-agent agreed with codex
  and went further — a *third* candidate document (`bin/orama-system/
  SKILL.md`) is what a separate navigator doc calls the actual
  agent-facing spine. Settled by: there are now three plausible "spine"
  documents and zero stated precedence — a real, if small, structural gap.
- **Is the PT↔orama bridge circular/friction?** The brief called it
  friction. Codex partially disagreed (no literal Python import
  circularity). Cursor-agent settled it decisively by quoting the actual
  architecture doc's own "Error 1" section, which names the current
  PT-owned-contracts design as **the fix** for a previously real
  circularity problem — not a new one.
- **Are the root-level `AGENTS.md`/`CLAUDE.md`/etc. files "identical"?**
  The brief said so. Both critiques disagreed, but cursor-agent proved it
  with a real `diff` (line counts differ 15-30%) and correctly separated
  "duplication that's a maintenance risk" from "divergence that's
  intentional architecture" (PT's full agentic-stack portable brain vs.
  orama's thin adapter for `GEMINI.md`/`ANTIGRAVITY.md` specifically).

## Why the plan ended up with four items, not forty

Every finding from either critique got checked against work *already
done* before being added to the plan: `docs/plans/2026-07-22-frugality-
privacy-reconciliation-and-navigator-closeout.md` (the model-routing gate
was already designed, decided, and landed — not open) and `docs/plans/
2026-07-22-cross-repo-out-of-scope-closure.md` (the tri-repo-alignment
plan's "active resume anchor" header looked stale but was already
dispositioned item-by-item on 2026-07-22). Re-litigating settled work
would have inflated the plan without adding real value — the four items
that survived are the ones no prior pass had already resolved.

## Cross-references

- `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md` — the "verify,
  don't average" gold nugget this arc is the source of.
- The plan document itself (path above) for the actual four fixes.
