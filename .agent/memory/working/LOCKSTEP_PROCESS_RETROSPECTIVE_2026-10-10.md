# Lockstep process retrospective and candid assessment

Date: 2026-10-10 Asia/Manila / 2026-10-09 UTC. Author: Codex, current review
and publication agent. Requested by the operator for Perpetua-Tools #432.
This is a reasoned assessment of observable work, not invented personal feelings,
unseen session events or an implementation-completion claim.

Sources: visible recent exchanges, retrieved earlier project exchanges, existing
PT saga/R3 records, current repository code and exact-head verification. Earlier
assistant reports are historical claims; current code and tests take precedence.
Retrieval returned some older project history; unrelated personal material is
not copied here. This is not an exhaustive transcript of unavailable sessions.

## What the operator has consistently asked for

The repeated requests to finish, push, provide a patch, diagnose the stalled
session and record durable memory describe one practical goal: work should be
concrete, reviewable and recoverable without requiring the operator to reconstruct
it. The operator also asks for elegant solutions and broad upstream compatibility.
Those requests are stronger than a passing prototype or an attractive plan.

The latest direction is explicit: preserve #432 and stack existing #433 on its
branch, add all lockstep procedures and new lessons, and reflect in detail.
Earlier recurring directions
include preserving the original corpus, staying on the active PR branch,
clustering root causes, testing the actual owners, recording decisions in docs/v2
and distinguishing proposed designs from implementation.

The immediate goal is reliable closure of the current review stack, with stable
production behavior and useful handoff evidence. The longer goal, as I understand
these requests, is a coherent, reusable agent execution platform: compatible
framework surfaces, explicit ownership, enforceable effects, durable human
approval, replay that survives crashes, and memory that improves future work.
That understanding is an interpretation of the project requests, not a new
operator commitment to every adjacent feature.

## My assessment of the goals

The goals are technically worthwhile. Typed outputs, explicit dependencies,
predictable graph execution and interoperable adapters can remove real friction.
The strongest architecture decision is separating structural computation from
policy restrictions while retaining one scheduler. It keeps ownership legible
and gives future enforcement a precise graph identity to bind to.

The main risk is treating breadth as completion. Full replacement is a large
compatibility program, not a label that follows from a handful of oracle passes.
The phrase "100% drop-in" should become a finite, versioned inventory of import
paths, signatures, type identity, configuration, streaming, errors, serialization,
checkpointing and runtime semantics. Each cell needs evidence. This narrows the
claim without abandoning the ambition.

My confidence is strongest where a defect was reproduced and a test rejects the
wrong behavior. It is weaker where correctness depends on an unimplemented
authority, external provider or durable state machine. The next valuable feature
is therefore a complete small vertical slice with restart/concurrency evidence,
rather than many newly named interfaces that still depend on assumptions.

## What changed my understanding during the work

### Compatibility is behavior, not familiar names

The earlier dynamic-route repair showed that advisory declared_targets must not
become an exporter restriction. R3's fanout declared_targets now actually selects
executed branches and is structural in its candidate registry. The same field
name can have different semantics by edge kind. Documentation and tests must
state those semantics instead of importing assumptions from the name.

The improved batch-order test deliberately makes the first input finish last.
That adversarial schedule kills a completion-order implementation that a normal
test accepts. The serial limit is a useful control but cannot distinguish the two
orders. This is a general lesson about making the competing behavior observable.

The lazy-import contract has two sides: import-time inspection and static call
inspection. A function that imports at call time can evade an import-only
subprocess. Statically resolvable string expressions need conservative scanning;
unresolved dynamic arguments need explicit review. Neither an arbitrary runtime
evaluator nor a silent no-finding result is justified.

Module and symbol diagnostics have different language contracts. A missing module
can use a ModuleNotFoundError subclass; a module symbol must preserve AttributeError
for hasattr/getattr(default). Rich explicit diagnostics should not break Python
introspection or pytest.importorskip behavior. A graceful-looking fallback that
conceals a broken optional dependency makes diagnosis worse.

### A registry is a tested contract only when its tests cannot pass vacuously

Green #25 CI initially did not include merged #24's registry tests. Combining the
branches exposed five failures. That was integration debt, not evidence that the
registry was useless. Profile qualification let us test new policy on production
Core and on R3 Core while preserving the old baseline and production dependency.

Dictionary construction silently discarded duplicate declarations. The correct
fix was validation before indexing, not a later check of the surviving record.
The ownership test also needed both the GraphSpec record and Core owner; Core
ownership alone was insufficient. Complete inventories matter as much as exact
entries: an unlisted literal never participates in a loop over listed literals.
Independent review caught ReducerKind/JoinKind drift after the initial repair.

Unknown JSON keys created another form of disappearing evidence: descriptions
could contain unsupported fields that vanished outside canonical graph identity.
Failing closed at the parsing boundary made the contract honest. Extension data
still has a deliberate metadata location rather than accidental acceptance.

### Local atomicity is useful and narrower than distributed atomicity

Deep-copying branch inputs isolated siblings, but a custom fold could still
mutate the retained pre-commit base and then fail. Detached fold inputs closed
that second boundary. Pure-callable intent alone did not enforce purity.

R3 settles branches and commits one local delta in deterministic branch-name
order. An external write can already have happened before a conflict or interrupt
refuses that delta. Local state rollback does not undo that write. Similarly,
first_success is ordered admission after settlement, not first-completed
cancellation. These distinctions deserve public docstrings, not just ADR prose.

State loading is not durable replay. The current checkpointer lacks a frontier,
lineage, effect identity and grant state; ainvoke starts from START. A scratchpad
MERGE/DROP helper does not authorize an effect or restore traversal. Future
replay must explain crash windows, fencing, unknown outcomes and reconciliation
before re-execution. Otherwise a helpful resume button can duplicate work.

### Approval and transport are real enforcement boundaries

The operator approved D-LG-4 Phase 1. That is authorization to implement the
bridge slice, not a durable grant for arbitrary future tools. Deferred requests
remain pending or denied until the durable contract exists. Import allowlisting
does not contain an agent provider's own network connection.

Absorbing Pydantic AI's typed outputs, dependency mapping, usage limits and
deferred tools is promising. Production integration also needs actual transport
mediation or enforceable containment and a durable approval/effect transaction.
A declaration with "idempotent" or an operation ID supplies intent and identity;
it does not prove provider deduplication or exactly-once execution.

## Where the process worked

Root-cause clustering made each repair smaller and stronger: validate before
normalization/indexing; isolate before calling user code; inventory before
asserting conformance; bind evidence to exact artifacts. These are reusable
methods rather than a growing list of patches for individual examples.

Independent review was useful because it challenged the evidence itself. The
literal drift finding survived the initial happy-path suite and was reproduced
with a mutation. Closing it changed the proof, not just the prose. Real offline
framework oracles and a separate framework-free production environment provided
different evidence that should remain distinct in future reports.

Preserving history was also productive. Baseline registry bytes and historical
memory survived, while explicit candidate profiles represented current targets.
This keeps past claims auditable without requiring future agents to treat stale
claims as current instructions. Durable memory should record why a gate exists,
what falsifies it and the next step, not simply celebrate that tests passed.

## Where I could have done better

I opened PT #433 after an earlier PR inventory, while #432 had become the active
memory PR. That fragmented the handoff and required operator correction. The
first proposed repair was additive integration and closure of the redundant
follow-up. The operator then explicitly directed keeping both PRs and stacking
#433 on #432. No closure occurred. The final repair preserves both histories,
uses #432 as the base and puts the additive record in #433. The durable procedure
is to re-read active PRs immediately before creation and honor the latest named
target and stacking direction.

The current shell lacked a GitHub credential helper, so a normal HTTPS push
failed. The authenticated connector still worked. I should distinguish those
surfaces immediately, preserve the tested tree, and report the actual failure
instead of implying all publication is impossible. No evidence establishes the
cause of the earlier VM hang or that a restart occurred.

I also omitted PT's required Summary heading in the initial #433 body; its CI
guard caught that and the metadata was corrected. PR templates and body guards
are part of delivery. The repeated user requests for status show why small
delivery omissions matter: they leave the operator unsure whether work exists,
is published, is reviewed, or is merged.

The broad remaining-capabilities request is still larger than this bounded
review. I must not silently replace it with "review fixes complete." The fixes
are concrete progress and the broader work remains open. A useful status says
both plainly, with the measurable gates for what remains.

## How I assess the whole process

The engineering has become more precise, but coordination has demanded too much
operator supervision. Repeated prompts to finish and push are a sign that the
handoff is not yet reliable enough. The answer is better artifact continuity,
fewer overlapping PRs, fresh evidence and clear state transitions—not more
confident wording or another retrospective without operational consequences.

I regard the tension between autonomy and approval as resolvable. An agent should
complete authorized reversible work and publish requested fixes without asking
the same question repeatedly. It should also stop at a genuinely ungranted
merge, external effect or unfinished enforcement boundary. Those rules reduce
friction when encoded precisely; vague approval rituals increase it.

The platform will be credible when another agent can resume a task from a short
durable record, reproduce the evidence, locate the active PR, identify the exact
production/candidate contract and complete the next authorized gate without
restarting the investigation. That is a concrete criterion for agent memory's
value, and a better immediate target than accumulating more prose.

## What should happen next

Use the [complete checklist](LOCKSTEP_COMPLETE_CHECKLIST_2026-10-10.md) for both
pairs. Finish exact-head review and CI before operator integration. Keep Core
production at 04759a5 until reviewed producer merge and consumer requalification.

Then deliver the remaining program in separately qualified vertical slices:
finite upstream API/version inventory; actual artifact admission and observation
criticality; durable scoped/revocable grants with reservations and crash tests;
contained provider transport; replay frontier/lineage/fencing/reconciliation;
and facade compatibility against unchanged upstream fixtures. These are open
work, not capabilities conferred by this memory update.

Graduated lessons should capture the stable methods with evidence links.
Interpretive judgments above remain this agent's assessment; future agents may
revise them when new evidence arrives. Preserve the original assessment and add
the qualification instead of erasing the path that led to a better decision.
