# Lockstep operator decisions and blockers (2026-10-22)

Author: claude-fable-5 (identity not independently verified). Record only; it ratifies, merges and
promotes nothing. `ORAMA_GRANT_SERVING` stays unset. Source: the operator's instructions in the
session, the GossipBus board and the references folder listed at the end.

## Decisions given by the operator

| Decision | Effect | State |
| --- | --- | --- |
| Push the local docs follow-up on orama-system PR 432 and answer its two review threads | Done: commit `2f38f35` pushed (fast-forward), both threads answered with the requested wording and resolved | complete |
| Merge main into the two model-governance PR branches, then publish the governance deltas on them | Authorized; attempted | **blocked**, see below |
| Reuse Perpetua-Tools draft PR 458 for the memory record | Done: this note and one lesson are added to its branch | complete |
| Ignore the Alexandria source-authority question for now | Left untouched | deferred |
| Ratify Part 3 after hardening and verification | Not performed | conditions unmet, see below |
| Execute the next pin promotion or serving if appropriate | Not performed | not appropriate, see below |

## Merge of main into the governance branches: blocked by pre-existing gates

Both branches are far behind main (orama-system PR 381: 224 behind; Perpetua-Tools PR 422: 136
behind). The conflict resolution was prepared in throwaway worktrees and nothing was pushed:

* orama-system: three stale restored copies (a loop-graph README, an ownership registry, and the E1
  freeze draft) take main's version, which is byte-identical to main afterwards; `docs/LESSONS.md` keeps
  both sides (all 31 main entries plus the branch's own entry).
* Perpetua-Tools: the three append-only memory files take main's version and re-append the branch's
  four episodic records and one lesson; the rendered lesson view is regenerated.

The merge commits are rejected by the repositories' own pre-commit gates because those gates check
files that main already contains:

* orama-system: the OSSF-1 skill-structure gate rejects main's canonical `bin/orama-system/SKILL.md`
  (576-line body over the 500 ceiling, missing triggers and sections) and another canonical skill
  file (missing allowed-tools and boundaries).
* Perpetua-Tools: the memory-records gate rejects a graduated lesson already on main whose id is not
  derived from its claim.

Bypassing the gates (`--no-verify`) needs the operator's explicit approval for the single merge
commit, or main's debt has to be fixed first. Neither was done.

## Part 3 ratification: conditions the operator set are not yet met

The operator asked to ratify after hardening and verifying. The acceptance packet requires an exact
immutable commit, test evidence for bootstrap, identical retry and lower-floor rejection, and a
recorded operator decision. The Part 3 document's own crosswalk says no bootstrap or anchor-floor
implementation exists yet ("None yet"), PR 432 is unmerged so its head can still move, and the
anchor-floor gate is a proposal. A merge or an agent endorsement is not ratification.

## Pin promotion and serving: not appropriate yet

The runtime PRs 17 and 71 are unmerged; Part 3 is unratified; and the serving prerequisites remain
missing (real operator authentication and key binding, effect-v2 parser and registry, revocation and
cascade bodies, retention and archive, execution witness, production transport, governed callers).

## Open decisions

1. Approve a single hook bypass for each merge commit, or fix main's gate debt first.
2. Strict scope rule and the choice between the minimal and the reconciled governance deltas.
3. Part 3 acceptance scope (bootstrap anchor only versus more) and its exact commit.
4. Ollama benchmark authorization (Task 0) before any default flip.

## References

`2026-10-22-governance-delta-comparison-and-options.md`, `2026-10-22-five-upload-coverage-and-closeout.md`,
`2026-10-22-upload-member-mapping-verification-claude.md`, `2026-10-21-claude-session-analysis-and-ledger.md`
in the references folder, and board rows 5518, 5520 and the rows that follow.
