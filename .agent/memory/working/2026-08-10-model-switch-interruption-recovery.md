# 2026-08-10 — Model-switch interruption during side-effecting repo work

**Status:** working memory / incident reflection  
**Scope:** ChatGPT continuity, GitHub side effects, stacked-PR recovery, PT-orama
coordination  
**Caution:** this note records observed workflow behavior plus engineering conclusions.
It is not an OpenAI product specification.

## What happened

A long-running ChatGPT task was implementing a multi-repository ORAMASYS plan with
GitHub writes. During the run, the ChatGPT UI displayed a message that the systems
were taking more time and offered a retry with a faster model. The operator
accidentally selected the faster-model retry, observed the new execution moving in a
direction inconsistent with the established plan, and stopped it.

When the original workflow was resumed, the GitHub repository already contained
branch and commit state that did not cleanly match the expected trajectory. Because
every GitHub write used the same connected GitHub identity, Git history alone could
not prove which internal ChatGPT execution produced each side effect.

During recovery, the resumed executor also made its own mistake while probing
connector write semantics: transient placeholder create/delete commits were made.
The placeholder content was removed and the working tree was restored, but the
no-op commits remained in repository history. This is recorded explicitly rather
than attributed to the earlier retry.

## What we can and cannot conclude

### Observed

- The UI offered a faster-model retry while the original complex request was
  unresolved.
- After that retry was triggered, repository side effects existed that the operator
  considered inconsistent with the original trajectory.
- The operator stopped the retry.
- GitHub records the connected account and commit graph, not which internal ChatGPT
  model or configuration caused a connector call.
- The final working tree could be recovered without discarding the useful MCP
  design work.

### Not proven

- We cannot prove from GitHub which exact commits came from the faster retry versus
  another execution path.
- We cannot infer from the UI message alone that a specific safety check was the
  exact cause of the delay.
- We cannot treat a model/reasoning switch as having documented transactional
  semantics for external tool calls.

## OpenAI cross-references

Official sources consulted during recovery:

- Additional automated safety checks for some biological/cybersecurity requests:
  https://help.openai.com/en/articles/20001326
- GPT-5.6 in ChatGPT, including reasoning/speed options and automatic reasoning:
  https://help.openai.com/en/articles/20001354
- OpenAI Usage Policies:
  https://openai.com/policies/usage-policies/

The first help article says some requests can take longer while automated safety
checks run, and that seeing such a notice does not itself mean a policy violation.
It does **not** give us evidence that this particular interruption was caused by a
specific internal check. The correct operational stance is uncertainty, not
attribution.

## First-principles failure model

The underlying engineering problem is broader than one model switch:

```text
reasoning process A
    |
    +--> external side effects S1, S2 ...
    |
UI retry / model switch / interrupted stream
    |
reasoning process B
    |
    +--> external side effects ?
```

The conversational surface may look continuous while the **side-effect lineage is
no longer proven continuous**. GitHub remains durable, but the reasoning state that
motivated a write is not encoded in the commit itself.

Therefore any retry, switch, or interruption during a mutating workflow must be
treated as a possible **executor transaction boundary**. This is our engineering
inference, not an OpenAI guarantee about implementation internals.

## Recovery method that worked

1. **Stop new writes.** Do not continue from memory of what the prior executor
   intended.
2. **Re-read canonical remote state.** Record current `main`, feature branch tip,
   parent SHAs, changed files, and open PRs.
3. **Separate tree truth from history narrative.** A noisy branch can still contain
   good file blobs.
4. **Salvage verified content, not assumptions.** Inspect final-good files
   individually.
5. **Reconstruct from canonical base.** Create a clean Git tree from current `main`
   plus only verified blobs.
6. **Create one clean commit.** Do not ask reviewers to reconstruct an interrupted
   experiment chain.
7. **Build stack relationships structurally.** PR2's commit parent and GitHub base
   must both be PR1's exact tip.
8. **Record the incident.** Preserve uncertainty and our own mistakes, not a
   convenient blame story.

This procedure preserved the useful first-run MCP work while replacing the noisy
branch history with clean review artifacts.

## Durable rules

### Rule 1 — Retry means continuity is unproven

After a model/reasoning retry, interrupted stream, resumed automation, or executor
handoff during external writes:

- assume side-effect continuity is **unproven**;
- re-fetch remote state before the next mutation;
- verify repo, branch, base SHA, and intended file set.

### Rule 2 — Never test a write API with a real write

Do not create placeholder files or commits merely to discover connector behavior.
Prefer:

1. schema/tool discovery;
2. read-only fetch/search;
3. documented Git Data primitives;
4. only then the intended production write.

The transient placeholder episode demonstrates why capability discovery itself
must be side-effect free.

### Rule 3 — Content salvage can be safer than branch salvage

When a branch contains both valuable work and dubious history:

- identify known-good blobs and files;
- rebuild a tree from a trusted base;
- preserve semantic work while discarding accidental sequencing.

This is integrative recovery, not blanket revert.

### Rule 4 — Stacked PR correctness is a graph property

A prose statement that “PR2 depends on PR1” is insufficient. Verify:

```text
PR2 commit parent == PR1 tip
PR2 GitHub base     == PR1 branch
```

Only then is the stack separately reviewable with the intended delta.

### Rule 5 — Separate readiness domains

The MCP recovery also reinforced a design lesson:

- package/runtime readiness;
- client registration;
- provider authentication/terms.

These are separate states. A bootstrapper must never manufacture one state to
satisfy another.

### Rule 6 — Historical plans are evidence, not commands

Re-evaluate an approved plan against the current tree. If the semantics already
landed under newer architecture, add ownership and verification rather than
duplicating historical prose or code.

## Positive outcome

The interruption forced a better architecture and a cleaner review topology:

- first-run MCP readiness now has one cross-platform implementation owner;
- launchers stay lean;
- provider auth is no longer conflated with core readiness;
- ORAMASYS P0-P2 convergence is verified structurally instead of duplicated;
- PR2 is truly stacked by commit parent and GitHub base;
- PT P4 is being closed as a provider-agnostic Tier-5 primitive behind the
  existing canonical frugality gate.

## Future graduation candidate

This working-memory incident should be considered for semantic graduation after the
PR proves the recovery procedure in CI. Candidate claim:

> During any model/reasoning retry or executor handoff in a side-effecting workflow,
> treat external-state continuity as unproven until canonical remote state is
> re-read; salvage verified content onto a trusted base instead of trusting
> interrupted branch history.

Graduate through PT's canonical `learn.py` / `graduate.py` workflow rather than
editing `lessons.jsonl` by hand.
