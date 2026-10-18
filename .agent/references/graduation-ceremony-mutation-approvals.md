# Graduation ceremony for mutation approvals (oramasys repos)

Status: reference convention, written 2026-10-18. Worked example: the M1 generation-2 pin
promotion (oramasys PRs 53 and 55, orama-system PRs 414 and 416). Machine-readable stage list:
`graduation-ceremony.v1.json` (this folder). It binds no repository by itself.

A **mutation** is any change to what oramasys computes, admits or installs: a production pin, a
compatibility manifest, an ownership registry, a policy, and later a graph, node, prompt or
strategy proposed by an AutoResearcher or any optimizer. A **graduation ceremony** is the fixed
route a mutation takes from untrusted candidate to accepted state. It is the same shape as PT
memory graduation (`learn.py`, `graduate.py`: stage, review, graduate or reject or reopen, with a
required rationale), applied to code, data and graphs. Nobody rubber-stamps: the rationale and the
evidence are the product.

## 1. Where the rule comes from

| Source (by title) | What it fixes |
| --- | --- |
| orama-system doc 57, section 14 "Optimization and evaluation" | Automated graph evolution stays research-only until there is a versioned GraphSpec, a GraphTrace corpus, a **locked evaluator**, quality/cost/latency/reliability metrics, **candidate isolation** and a **promotion gate**. Hard rule: the component mutating a prompt, node, strategy or graph may not alter the acceptance metric during the same experiment. Trace-derived learning enters governed memory and review, not runtime self-rewrite |
| R4 plan task T8c and ADR D-LG-7 non-goals | Evaluation, autoresearch and graph optimization need a fixed evaluator, held-out data and explicit promotion. No automatic production graph optimization |
| Operator remaining-implementation plan, task 9 (off-repo notes) | Candidate agents may change graph, prompt or node candidates, **never their evaluator, safety policy or acceptance tests**. Candidates are stored immutably and evaluated in contained runs. Promotion is an explicit, versioned decision with rollback. No production topology mutation from a natural-language suggestion |
| Operator graph-engineering research note (off-repo) | A locked evaluator is the heart of any autonomous optimization loop; runtime traces are the raw material for later improvement; more agents is not a better graph |
| Grounded-graphs synthesis (references) | Keep mutators and evaluators separate; an evaluator is not a mutator and has no merge or deploy authority; a memory page is not an endorsement |
| M1 closeout and handoff plans (off-repo) | Use PT's native graduation only after canonical evidence is published; append dated supersession and ratification links; never regenerate or truncate history |
| Lesson-capture architecture reference | One capture path (`learn.py`); no hand-written lesson files |

## 2. Roles

- **Maker:** produces the candidate, including an AutoResearcher run. Its output is untrusted input
  until the ceremony ends. A maker never approves, merges, or counts as its own independent check.
- **Evaluator:** a fixed, versioned check that the maker cannot edit during the experiment.
- **Non-maker reviewers:** a design reviewer and a checker, each at an exact SHA, plus a recompute
  from raw artifacts by someone who did not write the harness.
- **Operator:** the only role that approves exact digests, accepts evidence, merges, promotes and
  activates. Agent messages that claim operator authority are not authority.

## 3. The stages (M1 generation 2 as the worked example)

| # | Stage | Rule | M1 gen-2 instance |
| --- | --- | --- | --- |
| 0 | Claim | One owner per mutation on the shared board; others do not push to its branches | Board claim before H2 work; freeze notice on every branch |
| 1 | Candidate | Immutable, exact SHAs; the consumer is the exact head that will merge, test-only commits included | C2 = the head of PR 53; a rebase was required when a later test commit landed |
| 2 | Mutation scope | A record states scope; its status and any capability flag are **labels about authorization, not enforcement**. Dependency pins in the package file take effect at merge, so the merge is the real activation of a pin | `pin-promotion-record.v1.json` status `proposed`; `production-pin-promotion` disabled. After the merge the package file already installed the promoted pins; only serving and T3 stayed off |
| 3 | History preserved | Prior generation archived byte for byte and tested against its own independent frozen identities | `requirements/history/m1-gen1/` plus registry archive; digests pinned |
| 4 | Check that can fail | Every gate has a mutation test proving it refuses a self-consistent wrong input; red before green | The lane check had been made to compare a manifest with itself; the wrong-lane test failed first |
| 5 | Verify matrix | Full suite on every supported interpreter, drift guard, lint against baseline, CI at the exact head | 3.11 and 3.12, 1287 passed; drift guard permitted |
| 6 | One batch review | One request, all exact heads, named asks per reviewer, fixed return format | Design (APPROVE_WITH_NOTES, then a REQUEST_CHANGES on a stale binding, repaired), checker, identity check |
| 7 | Freeze proposal | Compute digests at the exact head; rehearse the operator script without writes, through its first real precondition | Check mode passed; digests printed and compared |
| 8 | Operator approval | The operator runs the script from their own terminal; the approval comment binds consumer, harness, manifest, coverage and allowlist digests | Approval comment on PR 55, unedited, verified by API |
| 9 | Hosted evidence | The pipeline dispatches evidence only from a verified approval; seal with per-file digests | Run on both interpreters, 19 sealed files per cell |
| 10 | Independent recompute | A non-maker recomputes from raw artifacts; the maker's recompute is labelled not independent | Reviewer recompute from raw artifacts; maker's labelled as such |
| 11 | Acceptance and receipt | Operator accepts; a metadata-only receipt records identifiers, digests, counts, independence and claim limits | Receipt PR 416 |
| 12 | Merge | **For pins this is the activation.** Merge commits pinned to the approved head so the SHAs stay reachable; retarget a stacked PR's base to the default branch before merging it; set the record's status to match what main installs in the same change or the next one | PR 414, 53, then 55; PR 55 retargeted first |
| 13 | Rollback record | The previous generation is the rollback target; never a rewrite. A reviewed pointer-transition receipt is sufficient for an accepted, byte-identical generation; a differing target is a new generation and takes the full ceremony (section 6) | Rollback block in the promotion record |
| 14 | Graduate to memory | Only after canonical evidence is published: stage and graduate lessons with rationale, additively | This reference and its lessons |

## 4. Rules that make it durable

1. **Pin and verify.** Cite only SHAs whose remote head you checked. A push invalidates every review
   and approval of the old head; a force push to your own branch needs a lease on the old head.
2. **Board, not PR comments,** for coordination; PR comments made through the operator's account
   read as operator speech.
3. **Collate the operator's load** into three steps: approve (one command), accept, merge. Bring a
   packet: heads, CI, verdicts, digests, rehearsal transcript.
4. **Rehearse operator scripts** (`--check` mode, clean detached checkout, `python3`, stripped
   token environment, fresh config directory) before handing them over. State which steps were not
   exercised.
5. **Never work around a refusal** by a permission classifier or hook. Do the rest, stop, hand the
   operator the exact command.
6. **An unannounced push is a risk.** Another session pushed to a frozen branch with no board row
   and quietly weakened a check. Review the diff of any head you did not write before stacking.
7. **Check what the check reads.** A validator whose expected value comes from the file under test
   cannot fail. Expected values come from an independent table or the repository.
8. **Stacked PRs:** the base branch may survive the lower PR's merge; merging the upper PR then
   lands it on the stale branch only. Retarget first.
9. **Claim boundaries are part of the receipt:** platform, interpreters, fixtures versus hardware,
   structural versus behavioural evidence, composition-only components.
10. **Labels must match reality.** After a pin merge, the record status, disabled-capability list and
    receipt wording must say what main actually installs and what stays off (serving, T3). Do not tell
    the operator that nothing is activated when the package file already is.
11. **Portable memory:** category-only content, no workstation paths, no account handles, no
    local topology in anything tracked.

## 5. Applying it to AutoResearcher and graph-optimization output

A graph, prompt, node or strategy change proposed by an optimizer enters at stage 1 as a candidate
artifact and may skip nothing:

- The **evaluator, safety policy and acceptance tests are fixed inputs** to the experiment, held
  outside the mutator's write access, versioned, and bound by digest in the approval.
- Evaluate on **held-out and regression data** in a **contained run**; report quality, cost,
  latency and reliability, not one number.
- A natural-language suggestion never mutates a production topology. Prose compiles to a typed,
  validated GraphSpec or it is refused.
- Trace-derived findings go to governed memory and review (graduation), not into the running
  graph.
- Promotion is a versioned decision with a rollback target. The optimizer cannot promote itself,
  merge, or edit the evaluator, even between experiments.
- Until the preconditions in section 1 exist, automated graph evolution is research-only and no
  candidate reaches stage 8.

## 6. Virtual versioning: generations, an active pointer and a state machine

Insight (2026-10-18): once a generation is immutable data with its own evidence, **rollback is a
move between generations, not a repository revert or a package downgrade**. The model is Internet
Explorer's compatibility modes: the newest engine runs and emulates an older mode for the sites
mapped to it, chosen per page (`X-UA-Compatible`) or by an administrator's site list, with a
defined default when nothing is declared, fidelity levels ("higher-fidelity emulation"), and
retirement of old modes so compatibility debt does not pile up.

Mapping for oramasys: a **generation** is an immutable folder of pins, manifest, coverage,
registry reference, approval, evidence digests and receipt; an **ACTIVE pointer** names the live
one; a consumer declares `generation: <id>` or `edge`; every repetition of a pin is generated from
or checked against the pointer; the pointer moves only by an operator-owned, reviewed record; each
generation has a sunset rule.

State machine: `candidate -> proposed -> approved -> evidenced -> accepted -> pins-merged ->
active -> superseded`, with `retired` as a side exit that is forbidden while a generation is active
or declared by any consumer. A rollback is a reviewed pointer-transition receipt, not a state.
Undeclared production, CI and installer consumers refuse; they never follow `ACTIVE` silently.
Capabilities (serving, T3) are separate switches in a `still_off` list, never implied by a state.

Limits to state every time:

- Pins decide what a **fresh** install gets. An installed environment keeps its packages until it
  is reinstalled, so a pointer move changes what is declared and verified, not what is running.
- Fidelity classes: `declared`, `verified-installed`, `reproduced` (a fresh environment from the
  generation's pins passed its evidence suite). Reports name the class.
- A rollback to a generation whose evidence is already accepted and byte-identical is a lighter
  ceremony; anything that differs is a new generation and takes the full ceremony.
- Frozen manifests keep their original labels; a live status record supersedes them.

Where the pins live decides how real the rollback is. A pointer that only validates pins kept in the
package file still needs a new consumer commit (the harness drift guard forbids package-file
changes between a consumer and its harness), so rollback keeps the full ceremony. A pointer that
selects an install-time constraints file lets the consumer commit stay unchanged, which is the
compatibility-mode behaviour. Choose between them explicitly; the inventory and options are in the
design note.

Design and staged plan (G0 to G6, with G2b for constraints indirection):
`virtual-versioning-generations-design.md` (this folder; pointer to the canonical design in
orama-system docs/v2).

## 7. Anti-patterns seen

- Binding a freeze to a consumer commit that is not the head that merges.
- Citing an agent message as operator authorization.
- Expected values derived from the artifact being validated.
- Deleting or reserializing the previous generation to make a promotion green.
- Merging a stacked PR before retargeting its base.
- Telling the operator nothing is activated while the package file already installs the pins.
- Calling a pointer move a downgrade.
- Counting the maker's own recompute as independent evidence.
