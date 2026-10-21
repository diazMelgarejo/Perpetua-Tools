# E1 C2 Claude Addendum: after the slice 2 merges (2026-10-20)

**Author:** claude-fable-5, 2026-10-20 UTC. Additive to the Claude five-day chronicle and the Agnes,
Cline and Codex records in this directory; nothing in them is edited.
**Status:** record only. It ratifies, merges, promotes and activates nothing. `ORAMA_GRANT_SERVING`
stayed unset.

## 1. State after the merges

* Phylax #15 (`9b62b049`), Oramasys #67 and #68 (merge `17e827c4`), orama-system #425, #426
  (`ffa7cf63`) and #428 (`142dd91a`), and PT #452 (`53b51cff`) are merged; CI is green on all four
  mains.
* Part 3 is on main but still marked proposed. E1 itself is ratified at orama-system `59c623fa`.

## 2. What the re-run of interop evidence showed

* The shared probe (7 scenarios) passed from clean worktrees at the two mains.
* The scope-binding check (5) passed.
* The abandon and successor check written on 2026-10-19 **failed at S11**: slice 2 made the
  consumer's abandon authenticator a required fail-closed port, and the script never injected one.
  The product was right and the script was stale. A dated revision injects a channel-bound stand-in
  and adds a refusal scenario (S11b); the original is kept with a pointer to the revision. Lesson
  `1334106007e5`.
* Extending the shared probe in place was not possible: each repository's CI compares its copy byte
  for byte with the pinned counterpart's copy. The new scenarios therefore live in a new file in
  both repositories, guarded by a SHA-256 literal in each repository's own test. Lesson
  `d2e07ccc0a47`.

## 3. Stale artifacts handled

* The 10-16 and 10-19 handoffs and an untracked working note of the same day listed pull requests as
  open that had merged; each now begins with a dated superseded notice and keeps its original text.
* Work was split by file ownership between the two Antigravity workers on GossipBus, with a
  cross-review so that no maker countersigned their own lane. The spec is
  `references/2026-10-20-E1-C2-slice2-probe-lane-specs.md` (outside the repositories).

## 4. Lessons in this addendum

* `1334106007e5`: an out-of-repository check written before a required-port change is stale
  evidence.
* `d2e07ccc0a47`: a cross-repository byte-identity check pins the shared file; add a new file and a
  hash literal.

## 5. State at writing

Local branch only; not pushed. Merges, pin promotion and Part 3 ratification remain the operator's.
