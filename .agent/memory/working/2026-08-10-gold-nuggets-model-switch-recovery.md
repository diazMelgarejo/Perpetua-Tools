# Gold Nuggets - model-switch interruption and recovery

**Date:** 2026-08-10  
**Format:** compact working lessons journal; bullets are intentionally concise.

- A model/reasoning retry during external writes is a **possible executor
  boundary**. Re-read remote state before the next mutation.
- Conversation continuity is not the same thing as **side-effect lineage
  continuity**.
- Git records commits and trees, not the internal reasoning process that caused a
  connector call.
- If attribution cannot be proven, record uncertainty. Do not manufacture a clean
  blame story.
- A UI delay/safety-check notice is a latency/safeguard signal, **not proof of a
  policy violation or exact internal cause**.
  Official context: [Additional automated safety checks](https://help.openai.com/en/articles/20001326)
- Reasoning/speed/model choices can differ for complex ChatGPT work. Operationally,
  verify state after a retry rather than assuming inherited intent.
  Official context: [ChatGPT model and reasoning options](https://help.openai.com/en/articles/20001354)
- Usage-policy safeguards surround the system, but repo recovery should be driven
  by observable Git state, not speculation about moderation internals.
  Policy: [OpenAI Usage Policies](https://openai.com/policies/usage-policies/)
- **Never probe a write API by making placeholder writes.** Discover schemas and use
  read-only calls first.
- When branch history is noisy but files are good, **salvage blobs onto a trusted
  base** instead of throwing away valuable work.
- "Revert everything" and "trust everything" are both lazy recovery strategies.
  Integrative recovery classifies each artifact.
- Stacked PR correctness is structural: `PR2 parent == PR1 tip` and
  `PR2 base == PR1 branch`.
- Historical plans are evidence, not executable scripture. Re-audit against current
  code before applying old diffs.
- One canonical owner per concern limits divergence when executors change mid-task.
- Package readiness, MCP client registration, and provider authentication are three
  different states. Never fake one to satisfy another.
- Launchers should orchestrate; requirement gates should verify/repair; provider
  tools should authenticate. Keep boundaries narrow.
- Feature flags must be explicit. Credential presence must never silently enable
  paid execution.
- Policy gates and execution pipelines are different abstractions. The pipeline must
  pass through the gate, not become another router.
- Prompt contents do not belong in frugality telemetry. Trace tier, recipe, stage,
  model, and budget metadata instead.
- Append-only memory is valuable precisely when the incident is embarrassing.
  Preserve our own mistakes too.
- A recovery is complete only when the clean review artifact is easier to understand
  than the incident that produced it.
