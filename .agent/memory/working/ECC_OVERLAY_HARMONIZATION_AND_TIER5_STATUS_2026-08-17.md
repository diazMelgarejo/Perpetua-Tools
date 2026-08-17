# ECC Local Runtime Overlay, Multi-Harness Harmonization & Tier-5 Status Report

**Date:** 2026-08-17  
**Branch:** `rebase/tier5-asgi-harmonized-20260814` (Perpetua-Tools [PR #356](https://github.com/diazMelgarejo/Perpetua-Tools/pull/356))  
**Commit:** `3ea86898`  

---

## 1. Executive Summary

This report records the complete resolution of CodeRabbit review findings on Tier-5 pipelines and cloud coder routing in Perpetua-Tools PR #356, along with the verification and harmonization of the **Everything Claude Code (ECC)** local runtime overlay across `.antigravity/*`, `.gemini/*`, `.claude/*`, and `.env.example`.

---

## 2. Multi-Harness Architectural Integration & Synergy

The ECC tools layer is harmoniously integrated, interleaved, and synergized across repository-level and user-global configurations:

```mermaid
graph TD
    subgraph Global Environments
        A[~/.claude: 67 Agents, 278 Skills, 94 Commands]
        B[~/.gemini: Antigravity CLI, Skills Catalog, Config]
        C[~/.antigravity: Extensions, MCP Config]
    end

    subgraph Repository Layer
        D[vendor/ecc-tools: Submodule c9de8f5b]
        E[scripts/git/ecc-local-overlay.tsv: 5 Reviewed Overlays]
        F[.env.example: Integrated Keys & Endpoints]
    end

    A -->|Mirrored & Bound| D
    B -->|Ingests & Interleaves| D
    C -->|Shared MCPs| D
    E -->|Applied cleanly via ecc-submodule-sync| D
    D -->|Synthesized templates| F
```

### Harmonization Matrix

| Harness / Layer | Integration Path | Synergized Role & Guarantees |
| :--- | :--- | :--- |
| **`.gemini/*` & `.antigravity/*`** | `.antigravity/ANTIGRAVITY.md`<br>`.gemini/ANTIGRAVITY.md` | Establishes Gemini/Antigravity workflow (planning before editing, test-first TDD, immutable updates, zero hardcoded secrets). Integrates with skill catalog (`find-skills`, `make-interfaces-feel-better`, `eval-harness`). |
| **`.claude/*`** | `~/.claude/` & `.claude/hooks/.logs/` | Parity with canonical 67 agents, 278 skills, and 94 commands. Preserves hook execution and telemetry logging without working-tree noise. |
| **OpenAI / Codex** | `.agents/skills/frontend-design/agents/openai.yaml` | Cross-harness agent manifest enabling OpenAI/Codex dispatch for production UI/UX design. |
| **Environment Template** | `.env.example` | Unified configuration template with Anthropic, Gemini (`GEMINI_API_KEY`, `GEMINI_API_KEY_2`), Perplexity, GitHub tokens, and local inference endpoints. |

---

## 3. Tier-5 Pipelines & PR #356 CodeRabbit Remediations

All review comments and outside-diff invariants on **PR #356** were addressed and verified:

1. **Model Context Window Correction (`config/models.yml`)**:
   - `grok-4.5.context_window` corrected to `333,000` (down from `1,000,000`).

2. **Cloud Coder Wire-Up & Model Scoping**:
   - `src/perpetua_tools/agent_launcher.py`: Scoped `PERPLEXITY_CODER_MODEL` and `ANTHROPIC_CODER_MODEL` before falling back to `CLOUD_CODER_MODEL`.
   - `src/perpetua_tools/alphaclaw_bootstrap.py`: Added provider mappings (`perplexity`, `anthropic`) with API keys and base URLs in `build_openclaw_config()`.
   - `tests/test_alphaclaw_bootstrap.py`: Added unit test coverage for single-key cloud coder configurations.

3. **FastAPI & Pydantic Validation (`orchestrator/fastapi_app.py`)**:
   - Added `@field_validator("prompt")` on `TieredPipelineRequest` to reject empty or whitespace-only prompts.
   - `tests/test_tiered_pipeline_endpoint.py`: Added 402, 502, 503 HTTP status mapping and runner state cleanup tests.

4. **Security & Model Registry Provenance**:
   - `tests/test_model_transport.py`: Verified rejection of non-Tier-5 targets, unallowed hosts, and mismatched provenance.
   - `scripts/check_model_ids.py`: Optimized registry scanning to avoid duplicate YAML parsing and added documentation authority tests.
   - `tests/test_control_plane_auth.py`: Asserted `CORSMiddleware` remains outermost in the middleware stack.

---

## 4. Verification Suite Results

- **`pytest`**: **215/215 passed** (100% green across all unit, integration, and endpoint suites).
- **`check_local_runtime_overlay.py`**: **OK** (All 5 overlay paths verified).
- **`ecc-submodule-sync.sh restore`**: **OK** (4 re-applied, 1 already applied).
- **`scan-tracked-banned-tokens.sh`**: **OK** (No banned patterns in tracked files).
- **`check_model_ids.py`**: **OK** (All configured models match source provenance).

---

## 5. How Latest ECC Integrates with Hermes (Read-Only Architectural Overview)

In the latest **Everything Claude Code (ECC v2.0.0)** ecosystem, integration with **Hermes Agent** is structured around a symbiotic **Operator Shell $\leftrightarrow$ Reusable Workflow Engine** separation of concerns:

```mermaid
graph TD
    subgraph Hermes Operator Shell
        H1[Interactive Session & Terminal REPL]
        H2[Channel Bindings & Notifications]
        H3[Local Task Delegation Loop]
    end

    subgraph ECC Workflow & Intelligence Engine
        E1[67 Specialized Agents]
        E2[278 Workflow Skills & Rules]
        E3[Deterministic Shell & Node Scripts]
        E4[hermes-imports Sanitization Pipeline]
    end

    subgraph Multi-Lane Execution Topology
        L1[L-H1: Native delegate_task Subagents]
        L2[L-PT: Perpetua-Tools / OpenClaw Programmatic Bridge]
        L3[L-Fleet: Distributed LAN Background Queues via coord_pulse]
    end

    H1 --> E2
    H3 --> L1
    H3 --> L2
    H3 --> L3
    E4 -->|Sanitize & Export| E2
    E2 -->|Install via hermes-home.js| H1
```

### 1. Conceptual Model: Operator vs. Workflow Engine
- **Hermes Agent as the Operator Shell**: Hermes operates at the interactive runtime and session management layer. It governs terminal interaction, interactive task delegation, background observation loops, multi-channel messaging (Telegram/Slack/Discord), and local workspace lifecycle management.
- **ECC as the Reusable Workflow & Intelligence Layer**: ECC provides the canonical, portable library of 67 specialized subagents, 278 domain workflows/skills, and deterministic validation scripts that Hermes agents discover, mount, and execute.

---

### 2. Concrete Architectural Integration Points

#### A. Dedicated Installation Target (`scripts/lib/install-targets/hermes-home.js`)
ECC's installer natively supports Hermes as a first-class execution target alongside Claude Code CLI, Cursor, Gemini CLI, and Windsurf:
- **Target Path Resolution**: Automatically projects and installs ECC skills into `~/.hermes/skills/` (user-level) and `.hermes/skills/` (project-level).
- **Cross-Harness Parity**: Normalizes ECC YAML frontmatter (`name`, `description`, `metadata`) so Hermes agents can dynamically discover and trigger skills at runtime without syntax translation.

#### B. The `hermes-imports` Skill (`skills/hermes-imports/SKILL.md`)
A dedicated ECC skill that defines the formal sanitization and publication pipeline for operator loops:
- **Direction & Purpose**: Moves repeatable, high-leverage operator patterns from private Hermes workflows into clean, public ECC skills and release-pack artifacts.
- **Sanitization Invariant**: Mechanically strips workstation paths (`/Users/...`, `~/.hermes/...`), live API keys/tokens, private contact graphs, and account identifiers, replacing them with generic role anchors (`operator`, `workspace owner`) and repo-relative paths.

#### C. Cross-Harness Bridge & Delegation Taxonomy
In the unified multi-agent topology (Perpetua-Tools + Orama-System + OpenClaw + Hermes), execution is routed through three strict, non-overlapping lanes:
1. **Lane L-H1 (Native Hermes)**: Interactive child `AIAgent` instances spawned directly within the Hermes process via `delegate_task`.
2. **Lane L-PT (Perpetua-Tools Bridge)**: Programmatic dispatch where Perpetua-Tools or OpenClaw invokes Hermes (`hermes_harness.py` / `spawn_hermes_agent()`) to execute an ECC skill in an isolated subagent workspace.
3. **Lane L-Fleet (Distributed Fleet)**: Queue-driven asynchronous background jobs dispatched across distributed LAN nodes via `coord_pulse`.

---

### Summary
In the latest ECC architecture, Hermes is treated not as a competing framework, but as an **execution harness**: ECC supplies the domain skills, immutable rules, and specialized agents, while Hermes provides the interactive operator shell, messaging channels, and autonomous execution loop.

