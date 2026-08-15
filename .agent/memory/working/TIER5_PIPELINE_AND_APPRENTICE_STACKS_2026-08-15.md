# Tier-5 Pipeline & 4 Competing Apprentice Recovery Stacks

**Date:** 2026-08-15  
**Topic:** Origin of `PIPELINE_FAST_MODEL`, `PIPELINE_STRONG_MODEL`, and the 4 Competing Candidate Stacks  
**Source Ref:** Commit `609d0b43` on `feat/v1-p4-tier5-pipeline-and-recovery-memory` (PT PR #350)  
**Methodology:** OramaSys / AFRP Type B (Expert) / "Synthesize, never amputate"

---

## 1. Overview & Root Origin

The environment variables `PIPELINE_FAST_MODEL` and `PIPELINE_STRONG_MODEL` were introduced in commit `609d0b43e2fbe9823b5dcadbe23da0adb1dd3395` on 2026-08-10 during the **Interrupted Reasoning & Tier-5 Frugality Recovery Arc**.

### Tracked Definition in `config/pipelines.yml`
```yaml
version: 1
provider: openrouter

# Tier-5 paid execution is opt-in. Model IDs come from runtime environment so
# this tracked config does not fossilize provider-specific model names.
models:
  fast:
    env: PIPELINE_FAST_MODEL
  strong:
    env: PIPELINE_STRONG_MODEL

limits:
  max_total_tokens: 8192

recipes:
  classify_then_generate:
    - name: classify
      model: fast
      max_tokens: 256
    - name: generate
      model: strong
      max_tokens: 4000
      input_from: classify
```

---

## 2. The 4 Competing Stacks & Apprentice Lineage

During the 2026-08-10 recovery event, four distinct candidate stacks were developed in parallel across the multi-agent network before the Senior Systems Architect executed the final integrative synthesis:

### 1. Apprentice-01
- **PRs / Lineage:** `orama-system` PR #299 + PR #300, paired with `Perpetua-Tools` PR #347.
- **Core Architecture:**
  - Pins reviewed upstream `ai-cli-mcp@2.22.0`.
  - Preserves `start.sh` as a thin launcher by delegating to a composed `scripts/ensure_requirements.sh`.
  - Separates core MCP readiness from provider auth / consent.
- **Disposition:** Reviewed and preserved in memory (`2026-08-10-oramasys-apprentice-01-voice-memory.md`).

### 2. Apprentice-02
- **PRs / Lineage:** `orama-system` PR #301 + PR #302, paired with `Perpetua-Tools` PR #348.
- **Core Architecture:**
  - Emphasizes fail-soft launcher resilience (`|| true`).
  - Strict Node engine verification (`>=20.19` or `>=22.12`).
  - Validates `ai-cli doctor` and `ai-cli models` explicitly before Claude MCP registration.
- **Disposition:** Reviewed and preserved in memory (`2026-08-10-oramasys-apprentice-02-voice-memory.md`).

### 3. Senior Working Base
- **PRs / Lineage:** `orama-system` PR #303 + PR #305, paired with `Perpetua-Tools` PR #349.
- **Core Architecture:** The Senior Systems Architect's baseline, built directly on clean `origin/main` without transient prototype commits.
- **Disposition:** Formed the working substrate for final cross-stack synthesis.

### 4. Final Senior Integration
- **PRs / Lineage:** `Perpetua-Tools` PR #350 (Branch `feat/v1-p4-tier5-pipeline-and-recovery-memory`, commits `609d0b43`…`f311aaa0`).
- **Core Architecture:**
  - Governed Tier-5 pipeline execution in `orchestrator/tiered_pipeline.py`.
  - Injected runtime model identity via `PIPELINE_FAST_MODEL` and `PIPELINE_STRONG_MODEL` to prevent provider model fossilization in tracked YAML.
  - Verbatim memory preservation of Apprentice-01 and Apprentice-02 records following the "Synthesize, never amputate" doctrine.
- **Disposition:** Canonical merged baseline.
