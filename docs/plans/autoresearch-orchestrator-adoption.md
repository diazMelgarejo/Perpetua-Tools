# AutoResearch Orchestrator Adoption Plan

Status: canonical adoption plan for Perpetua-Tools main.
Primary upstream: `uditgoenka/autoresearch`.
Secondary audit reference: `karpathy/autoresearch` only.

## Goal

Adopt AutoResearch as a real, operational research substrate without creating a parallel orchestration path.

Perpetua-Tools remains the runtime/state authority. orama-system remains optional methodology and planning refinement. AutoResearch supplies an upstream goal-directed research loop that Perpetua can plan, dry-run, install, sync, and dispatch safely.

## Upstream Sources

| Source | Role | Pin |
| --- | --- | --- |
| `https://github.com/uditgoenka/autoresearch` | Primary orchestrator/plugin/submodule source | `9f51f726e513be4e899b6afeed9f9c55fc1f51f3` |
| `https://github.com/karpathy/autoresearch` | Secondary catch-all audit reference for the original ML experiment loop | `c92bee55ebc339e8b1501f6b5c9cfb54835a9de8` |

Use uditgoenka for command semantics, archetypes, `--dry-run`, and autonomous orchestrator behavior. Use karpathy only when checking original ML-loop expectations such as `prepare.py`, `train.py`, `program.md`, single-GPU assumptions, `log.txt`, and `val_bpb`.

## Adoption Mode

Adopt both forms, like ECC:

1. Real submodule mirror: `vendor/autoresearch` tracks uditgoenka/autoresearch `master`.
2. Runtime plugin mode: `claude plugin marketplace add uditgoenka/autoresearch` and `claude plugin install autoresearch@autoresearch` remain idempotent runtime install steps.

The submodule is reference/source parity. Runtime still uses the existing bridge and plugin install path. Do not fork a new AutoResearch runner when `orchestrator/autoresearch_bridge.py` already owns that responsibility.

## Existing Paths To Reuse

| Responsibility | Existing path |
| --- | --- |
| Bridge, plugin install, local/GPU sync, preflight, dry-run planner | `orchestrator/autoresearch_bridge.py` |
| Bridge unit tests | `tests/test_autoresearch_bridge.py` |
| Migration details | `docs/wiki/05-autoresearcher-migration.md` |
| Agent navigation | `CLAUDE.md` |
| Skill routing | `SKILL.md` |
| orama AutoResearcher role | `orama-system/bin/agents/autoresearcher/SOUL.md` |
| orama v2 doctrine | `orama-system/docs/v2/25-autoresearcher-doctrine-and-againtra-flagship.md` |

## Existing Skills To Reuse

Do not create a new skill or methodology path until these are exhausted:

| Skill / guidance | Use |
| --- | --- |
| Perpetua `SKILL.md` | hardware/model routing and runtime rules |
| Perpetua `AGENTS.md` | repo-wide agent guardrails and endpoint policy discipline |
| orama `bin/agents/autoresearcher/SOUL.md` | AutoResearcher role behavior |
| orama `bin/orama-system/skills/oramasys-method/SKILL.md` | methodology and architecture-heavy synthesis |
| orama `bin/orama-system/skills/oramasys-method/references/integrative-merge.md` | cross-repo harmonization without deleting existing pathways |
| orama `bin/orama-system/skills/git-history-surgery/SKILL.md` | branch/rewrite analysis before judging stale work |
| ECC `vendor/ecc-tools` skills | subagent auto-selection and existing ECC-style skill conventions |

## Dry-Run First Contract

Long-running goals must start with a dry-run plan.

Perpetua v1 entry point:

```python
from orchestrator.autoresearch_bridge import preflight

plan = preflight(
    goal="harden gateway auth token handling",
    dry_run=True,
    use_orama=True,
)
```

Dry-run must not call:

- Claude plugin install or slash commands
- GPU runner
- SSH
- SCP
- LM Studio HTTP probes
- git sync/bootstrap
- paid/cloud model APIs

Dry-run may read local `swarm_state.md` and may run deterministic, local, cheapest-first classification.

Future v2 API candidate:

```http
POST /autoresearch/plan
```

The v2 endpoint must preserve the same dry-run rule: planning returns state, goal, archetype, pipeline, predicate, and safety gates only.

## Goal Archetypes

Keep names aligned with uditgoenka/autoresearch `guide/autoresearch-orchestrator.md`.

| Archetype | Pipeline | Perpetua meaning |
| --- | --- | --- |
| `fix-broken` | `debug -> fix -> regression` | Reproduce and clear failing behavior |
| `ship-ready` | `regression -> fix -> ship` | Make the target releasable, with HITL before ship |
| `optimize-metric` | `plan -> core-loop` | Improve a declared metric, including `val_bpb` |
| `harden` | `security -> fix -> security` | Close security findings and prove no regression |
| `build-feature` | `scenario -> fix -> regression` | Build against acceptance tests |
| `explore` | `scenario` | Single-pass exploration |
| `document` | `learn` | Documentation and lessons update |
| `decide-design` | `reason` | Architecture decision and tradeoff analysis |
| `what-to-build` | `improve` | Opportunity ranking and next experiment |

## Perpetua vs orama Responsibilities

Perpetua owns:

- runtime state and dispatch
- plugin install idempotency
- local/GPU sync
- GPU guard via `swarm_state.md`
- dry-run plan object
- hardware and model frugality rules

orama owns, when available:

- methodology refinement
- critique/rubric application
- CIDF/orama reasoning framing
- optional multi-agent review of the Perpetua plan

Perpetua should pass only state, goal, archetype, predicate, pipeline, and safety gates to orama. orama must not reach directly into Perpetua runtime internals or execute plugin/GPU actions during dry-run.

## Efficiency And Cost Rule

Use cheapest-first execution:

1. Deterministic local classifier and repo state.
2. Existing local models and local search/indexes.
3. Free or already-configured online tools if local evidence is insufficient.
4. Paid/cloud LLM escalation only when necessary and explicitly justified.

Do not spend expensive reasoning on classification that `orchestrator/autoresearch_bridge.py` can compute deterministically.

## Idempotency And Non-Regression Rules

- Preserve plugin install idempotency.
- Preserve local and GPU sync idempotency.
- Preserve `uv sync --dev` bootstrap behavior.
- Preserve GPU guard: no dispatch while `swarm_state.md` reports `GPU: BUSY`.
- Preserve user-controlled env overrides: `AUTORESEARCH_REMOTE`, `AUTORESEARCH_BRANCH`, `LOCAL_AUTORESEARCH_PATH`, `GPU_BOX`, and `GPU_REPO_PATH`.
- Do not regress to a hardcoded GPU-only, script-only, or karpathy-primary model.
- Do not create a new pathway where the existing bridge can be upskilled.

## Minimal Implementation Stage

Current main should contain:

1. `.gitmodules` entry and gitlink for `vendor/autoresearch`.
2. `orchestrator/autoresearch_bridge.py` dry-run/autoplan support.
3. Tests proving dry-run skips plugin/sync/LM Studio/GPU work.
4. Cross-links from wiki, `CLAUDE.md`, `SKILL.md`, and orama AutoResearcher docs.

## Follow-Up Architecture

Later work may add:

- `POST /autoresearch/plan` in the v2 oramasys API.
- Shared endpoint contracts for plan serialization.
- Richer orama methodology modulation.
- Automated upstream diff audit against uditgoenka primary and karpathy secondary.

These are follow-up architecture tasks. They should not block the minimal dry-run/autoplan adoption path.
