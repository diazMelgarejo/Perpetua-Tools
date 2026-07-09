# Stray Folder Remediation

Date: 2026-07-09

## Endpoint policy contract

### Who / what / why

- **Who:** AI agents working the endpoint-policy/security wiring path, including the earlier agent that created `.agent/endpoint-policy-contract.yml` and the later cleanup pass that followed the checker path too literally.
- **What happened:** The endpoint transport policy contract was repeatedly placed under `.agent/` paths. First it appeared at `.agent/endpoint-policy-contract.yml`; then it was moved to `.agent/protocols/endpoint-policy-contract.yml`; then a CI symptom fix recreated `.agent/endpoint-policy-contract.yml` because `scripts/security/check_endpoint_policy_core.py` still expected that broken path.
- **Why it happened:** Agents treated `.agent` as a generic policy drop zone and treated a failing checker as architectural truth. The correct ownership boundary is: reusable implementation/package lives in `packages/endpoint-policy/`; repo-level contract/config lives in `config/endpoint-policy-contract.yml`; `.agent` is portable brain memory, skills, protocols, and tools, not the endpoint-policy contract home.

### Current canonical state

The endpoint transport policy contract belongs at `config/endpoint-policy-contract.yml`. The reusable endpoint policy primitive lives as a subpackage under `packages/endpoint-policy/`. That subpackage carries its own Apache-2.0 license metadata, `LICENSE`, and `NOTICE`, so downstream consumers can adopt the contract without inheriting the host repository license.

### Lesson

When CI points to a path that violates repo ownership boundaries, fix the checker and backlinks instead of cargo-culting the broken path. Use `git mv` or an equivalent same-content move to preserve history, then update backlinks in a separate pass.

## `--help/` memory folder

### Who / what / why

- **Who:** A rogue or malformed agent invocation in the memory-render / learning workflow.
- **What happened:** A root `--help/` directory appeared with generated memory files:
  - `--help/LESSONS.md` — only a default rendered memory stub.
  - `--help/lessons.jsonl` — empty.
- **Why it happened:** A command likely passed or forwarded `--help` where a path argument was expected, causing the renderer or learner to interpret `--help` as an output directory rather than a flag. Because the generated files contained no unique semantic content, there was nothing to blend into `.agent/memory/semantic/`.

### Cleanup performed

- Deleted `--help/LESSONS.md` in commit `ed265d5`.
- Deleted `--help/lessons.jsonl` in commit `61b754a`.

### Lesson

Future agents must pass `--` before user-supplied strings that may start with `-`, validate output directories before generating memory files, and reject root-level flag-looking output paths such as `--help/`.

Canonical semantic memory remains under `.agent/memory/semantic/`.
