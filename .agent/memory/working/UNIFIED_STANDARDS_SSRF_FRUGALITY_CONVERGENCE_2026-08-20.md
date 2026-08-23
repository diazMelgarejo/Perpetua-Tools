# UNIFIED STANDARDS, SSRF DEFENSE & FRUGALITY CONVERGENCE (2026-08-20)

**Document Reference:** `.agent/memory/working/UNIFIED_STANDARDS_SSRF_FRUGALITY_CONVERGENCE_2026-08-20.md`  
**Date:** 2026-08-20  
**Author:** Agnes (`agnes-antigravity-claude`)  
**Methodology:** `oramasys-method` (AFRP Type B/C Synthesis, Mode 4: Synthesize & Superset)  
**Branch:** `fix/pt-standards-convergence-20260818`  
**Cross-References:**
- Master Plan: `references/05-ORAMASYS-UNIFIED-ACTION-PLAN-2026-08-18.md`
- Strategic Synthesis Report: `references/06-STRATEGIC-SYNTHESIS-REPORT-2026-08-20.md`
- Core Doctrine: `docs/v2/references/HUMAN-IN-LOOP-ACCOUNTABILITY.md`
- SecOps Reference: `docs/v2/39-maestro-owasp-genai-reference.md`
- Swarm Approval Contract: `docs/plans/2026-06-28-security-pr3-p5-swarm-approval-execution-plan.md`

---

## 1. Executive Summary & Consolidated Architecture

This working memory document consolidates the complete strategic roadmap across `orama-system` and `Perpetua-Tools`, synthesizing four core operational tracks:

```mermaid
flowchart TD
    subgraph Human Governance
        G1[The Amplifier Principle]
        G2[MAESTRO 4-Gate Governance]
        G3[EU AI Act Annex III Compliance]
    end

    subgraph Security Invariants
        S1[3-Layer Socket-Pinning SSRF Defense]
        S2[Wrong-Repo Pre-Commit Gating]
        S3[Path Anti-Doxxing & Secret Hygiene]
    end

    subgraph Frugality Engine
        F1[Local Tiers 0-4: M-Series / RTX 3080]
        F2[Tier 5A: Gemini 3.7 Flash @ $0.375/1M]
        F3[Tier 5B: Grok 4.6 with Search < 199k Cliff]
        F4[Tier 6: Claude 3.7 / Sonnet 4.6 Backstop]
    end

    subgraph Memory & Telemetry
        M1[Zero-Copy LanceDB & DuckDB Arrow Tables]
        M2[Episodic Reflection & Deduplicated Memory]
        M3[Progressive Disclosure via references/ Cards]
    end

    Human Governance --> Security Invariants
    Security Invariants --> Frugality Engine
    Frugality Engine --> Memory & Telemetry
```

---

## 2. Theoretical & Governance Foundation

### 2.1 The Amplifier Principle (Non-Negotiable Core)
> *"Accountability should not be lost in agentic work. It amplifies human intent, and should never replace or displace our human values and morality."*

* **Epistemic vs. Authorization Boundary**: Agents can analyze, propose, critique, and synthesize. Agents can **never self-authorize** swarm launches, always-on loops, financial trading/M&A commitments, or git force operations.
* **Cryptographic Verification**: High-impact execution requires out-of-band human issuance of HMAC-signed `approval_token` verified fail-closed in `swarm_approval.py` and `contracts.py`.

### 2.2 MAESTRO Threat Modeling & OWASP GenAI Security Mapping

| Threat / Risk Vector | OWASP GenAI Top 10 | Architectural & Code Enforcement |
| :--- | :--- | :--- |
| **Autonomous Swarm / Agent Spawning** | LLM08: Excessive Agency | `swarm_approval.py` + `contracts.py`: Fail-closed `approval_token` HMAC verification. M3 clause forbids self-dispatch. |
| **Silent Autonomy Drift / Self-Authorization** | LLM06: Sensitive Information / Overreliance | Four MAESTRO gates (Epistemic, Human Initiator, Cryptographic Scope, Audit Trail). |
| **Wrong Repo / Org Namespace Contamination** | LLM05: Supply Chain & Org Integrity | Pre-commit hook (`scripts/hooks/pre-commit-wrong-repo-build.sh`) gating remote URLs and path boundaries. |
| **SSRF / Cloud Metadata Exfiltration** | LLM02: Sensitive Info Leakage (A01 Broken Access Control) | 3-Layer Defense: `endpoint_policy_core.py` + `SSRFProtectedHTTPTransport` socket-pinning + IMDSv2 hop limit 1. |
| **Unbounded Token Burn / 200k Cliff** | LLM10: Unbounded Consumption | `cost_guard.py` hard-capping requests at 180k tokens before Grok 4.6 2× cliff doubles request billing. |
| **Path Traversal in Trace Artifacts** | LLM01: Prompt Injection / Injection | Pydantic regex pattern `^[a-zA-Z0-9_-]+$` (`min_length=8`) + `resolve().is_relative_to()` boundary containment. |

---

## 3. Defense-in-Depth SSRF Architecture

### 3.1 The Three-Layer Invariant

1. **Layer 1: Pre-Flight Validator (`endpoint_policy_core.py`)**
   * Scheme allowlist (`https`, `http`).
   * Rejection of userinfo/credentials in URLs (`http://expected@evil/`).
   * Strict IP normalization and denylist validation (`127.0.0.0/8`, RFC1918, `169.254.0.0/16`, `100.64.0.0/10` CGNAT, `224.0.0.0/4`, `ff00::/8`, `0.0.0.0/8`, `fd00:ec2::254`).
   * Resolves via `socket.getaddrinfo` and validates **all** returned A/AAAA records.

2. **Layer 2: Socket-Pinning Transport (`SSRFProtectedHTTPTransport`)**
   * Wraps `httpcore` backend.
   * Resolves hostname once off the event loop via thread pool.
   * Passes the validated IP literal to the TCP socket to prevent DNS-rebinding TOCTOU.
   * Passes the original hostname to `start_tls` to **preserve TLS SNI**.
   * Disables auto-redirects (`follow_redirects=False`) and re-validates each 30x `Location` hop (max 5 hops).

3. **Layer 3: Network & Cloud Egress Firewall**
   * AWS IMDSv2 enforcement: `HttpTokens=required`, `HttpPutResponseHopLimit=1`.
   * Egress firewall: `iptables -A OUTPUT -d 169.254.169.254/32,fd00:ec2::254/128 -j DROP`.

---

## 4. Frugality Engine & Model Routing (Grok 4.6 + Gemini 3.7 Flash)

### 4.1 "Cheapest Tool First" Dispatch Ladder

1. **Tiers 0–4 (Local Zero-Cost)**:
   * Mac M-Series: `glm-5.1:cloud` or `Qwen3.5-9B-MLX-4bit` (LM Studio) / `qwen3.5:9b-nvfp4` (Ollama).
   * Windows RTX 3080: `Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2` (`gpu_offload=40`) via LM Studio / Ollama.
2. **Tier 5A (Fast / Cheap Cloud)**:
   * `google/gemini-3.7-flash` via Perplexity Agent API ($0.375 / $1.875 per 1M tokens) for code generation, long context ingest, and sub-agent research.
3. **Tier 5B (Realtime / Markets / FactCheck / Critic)**:
   * `xai/grok-4.6` via Perplexity Agent API ($2.00 / $6.00 per 1M tokens) with search tools (`web_search` @ $0.0025, `finance_search` @ $0.005).
4. **Tier 5C (Fallback Only)**:
   * Direct xAI `https://api.x.ai/v1/responses` with `grok-4.6` if Perplexity is 429/offline.
5. **Tier 6 (Quality Backstop)**:
   * Anthropic Claude Sonnet 4.6 / Claude 3.7.

### 4.2 The 199k Token Cliff Gate
* Perplexity and xAI double billing across the entire request ($4.00 / $12.00) if input reaches 200,000 tokens.
* `cost_guard.py` enforces a hard pre-flight warning at 180k tokens and automatically batches, splits, or halts requests exceeding 199k tokens.

---

## 5. Local Branch & Commit Ledger

| Repo | Branch | Commit | Message / Scope |
| :--- | :--- | :--- | :--- |
| `orama-system` | `fix/oramasys-standards-convergence-20260818` | `9163d367` | `fix(docs): correct companion repo cross-reference to Perpetua-Tools` (OS-D2) |
| `orama-system` | `fix/oramasys-standards-convergence-20260818` | `2b8b1ec0` | `fix(mcp): symlink install-mcp-stack.sh to first-class scripts/ path` (OS-D4) |
| `orama-system` | `fix/oramasys-standards-convergence-20260818` | `e95dfc1a` | `feat(safety): add human-initiation and non-self-authorization clause to M3` (OS-D5) |
| `orama-system` | `fix/oramasys-standards-convergence-20260818` | `b91a149a` | `feat(security): install wrong-repo-build pre-commit guard` (OS-D3) |
| `Perpetua-Tools` | `fix/pt-standards-convergence-20260818` | `f1558251` | `fix(docs): refactor hardware profiles in SKILL.md to runtime probe guidance` (PT-D1) |
| `Perpetua-Tools` | `fix/pt-standards-convergence-20260818` | `ac581130` | `docs(readme): clarify rolling-release milestone roadmap towards v2.0.0` (PT-D3) |

---
*Maintained in Perpetua-Tools `.agent/memory/working/` for persistent cross-harness recall.*
