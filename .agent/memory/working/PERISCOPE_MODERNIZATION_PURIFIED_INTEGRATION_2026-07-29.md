# Periscope AgentsView modernization — purified integration decision (PR #20 over PR #17)

**Date:** 2026-07-29  
**Status:** decided — PR #17 closed; PR #20 is integration path  
**Scope:** periscope `merged` integration; cross-repo git doctrine

---

## Decision

| Item | Outcome |
|------|---------|
| [PR #17](https://github.com/diazMelgarejo/periscope/pull/17) | **Closed, not merged** |
| Branch `cursor/agentsview-modernization-3way-f559` | **Preserved** — permanent bad-example reference |
| [PR #20](https://github.com/diazMelgarejo/periscope/pull/20) `cursor/agentsview-purified-onto-kenn-f559` | **Chosen** integration candidate |
| Doc on `merged` | `periscope/docs/2026-07-28-AgentsView+Periscope-Fresh.md` addendum |

---

## Problem (PR #17)

`cursor/agentsview-modernization-3way-f559` had the **right product tree** but **wrong
replay ancestry**:

- Replayed ~769 upstream AgentsView commits from ancient merge-base `5f9e809f`
- Each upstream commit got a **synthetic SHA** (duplicate history, not inheritance)
- GitHub three-dot diff vs `merged`: **2,169 files / 769 commits**
- Only **9 commits** were truly Periscope-unique (`git cherry` vs `kenn-io/agentsview`)

Functionally: current AgentsView + Periscope treatment — but the graph is unusable for review.

---

## Solution (PR #20 — purified)

1. Base on **original** `kenn-io/agentsview` SHAs @ `6c3317ad` (#1283)
2. Cherry-pick **only** the 9 Periscope-unique commits (no upstream replay)
3. Align push-safe secret-scan test fixtures → **byte-identical tree** to PR #17 tip

---

## Comparison table

| Metric | PR #17 (bad replay) | PR #20 (purified) |
|--------|---------------------|-------------------|
| Merge-base with `merged` | `5f9e809f` (ancient) | `6c3317ad` (#1283) |
| Commits above `merged` (three-dot) | 769 | **9** |
| Files changed vs `merged` (three-dot) | 2,169 | **816** |
| Upstream SHAs | Synthetic replay | **Original kenn-io** |
| Periscope commits visible | Buried in replay | **On tip** |
| Tree vs PR #17 tip | reference | **byte-identical** |
| Merge | ❌ | ✅ candidate |

Symmetric tree diff vs `merged` (~2k files) is similar on both — honest modernization size.
PR #20 fixes **ancestry and reviewability**, not product scope.

---

## Policy: never synthesize SHAs

**Default:** never replay upstream under new SHAs when originals exist on `kenn-io/agentsview`
/ `origin/agentsview`.

**Exception — security/safety expunge only:**

- Leaked identities, workspaces, doxxing
- API keys, access keys, passwords, tokens in history
- Workstation paths or sensitive literals in tracked blobs
- GitHub push-protection (fixture rotation + history scrub)

Not allowed: synthetic SHA stacks for convenience, "fresh import" theater, or cleaner-looking PR graphs.

**Edge case:** `47ca74c` (last Wes commit before Periscope spec on `merged`) survives as
original SHA on `merged`; bad replay branch has `22cf1394` — same `%T`, wrong SHA.

---

## Bad-example branch (do not delete)

`cursor/agentsview-modernization-3way-f559` remains on GitHub as **what not to do**:

- upstream replay instead of upstream inheritance
- synthetic SHA stacks
- ancient merge-base → exploded PR diffs

---

## Cross-repo curriculum

| Repo | Path |
|------|------|
| periscope | `docs/2026-07-28-AgentsView+Periscope-Fresh.md` (addendum) |
| orama-system | `bin/orama-system/afrp/failure-modes.md` §8 |
| orama-system | `bin/orama-system/cidf/references/integrative-editing-examples.md` §10 |
| orama-system | `bin/orama-system/skills/git-history-surgery/references/path-scoped-pr-replay-reference-card.md` |
| orama-system | `bin/orama-system/skills/git-history-surgery/SKILL.md` §11 |

---

## Recall

```bash
python .agent/tools/recall.py "periscope purified integration PR20 synthetic SHA never replay upstream"
```
