# Oramasys v2 Session Memorial — 2026-06-29

## 🧠 Overview
This document memorializes the full Oramasys v2 execution session performed across:
- Perpetua-Tools
- Orama system integration patterns
- Cross-repo security + CI hardening design

It records architectural decisions, fixes, and invariants established during this session.

---

# 🚀 1. Core Outcomes of This Session

## 1.1 Security Architecture Completed
We established a full multi-layer security model:

### Layers
1. Policy Layer
   - endpoint_policy_core (SSRF-safe URL validation)
   - deterministic exception model (ModelEndpointPolicyError)

2. Runtime Layer
   - portal_server rendering safety
   - control plane authentication hardening

3. CI Layer
   - GitHub Actions enforcement for SSRF + auth + token leakage

---

## 1.2 SSRF & Endpoint Validation Invariants

### Final invariant:
> All external inputs must pass through a deterministic security boundary before execution.

### Key guarantees:
- No raw urlparse() usage outside policy layer
- No stdlib parsing exceptions escape boundary
- SSRF vectors blocked consistently (RFC1918, link-local, metadata IPs)

---

## 1.3 Scheme Preservation Fix (Critical Transport Bug)

### Root Cause
- Downstream model registry reconstructed URLs using hardcoded `http://`
- Upstream tilting discovery layer produced scheme-aware URLs

### Fix applied
- Preserve original scheme (http/https)
- Only default when scheme is missing
- Separate host extraction from transport reconstruction

### Added enforcement
- CI contract test ensures no scheme downgrade occurs

---

## 1.4 CI Security Guard Introduced

### Added checks:
- SSRF regression detection
- urlparse usage detection
- token leakage scanning
- auth boundary validation

---

## 1.5 Auth System Hardening

### Fix applied:
- Introduced `_secure_write_token`
- Enforced `0600` file permissions at creation time
- Eliminated umask-based token leakage risk

---

## 1.6 Portal Security Fixes

### Fix applied:
- All external inputs now HTML escaped
- Prevented XSS via event metadata and model outputs

---

## 1.7 Testing Strategy Enhancements

### Added:
- Scheme preservation contract test
- Endpoint fuzz / sentinel validation tests
- SSRF regression safety coverage

---

# 🧱 2. Cursor Execution System

A structured Cursor agent manifest was created:

- Auth hardening tasks
- SSRF enforcement tasks
- Portal sanitization tasks
- Windows script verification tasks (false-positive confirmed safe)

This enables deterministic agent execution of PR fixes.

---

# 🔗 3. Cross-Repo Architecture Decisions

## 3.1 Shared Security Core
- endpoint_policy_core is canonical validation layer
- both Perpetua-Tools and Orama must depend on it

## 3.2 No Divergence Rule
- SSRF logic must remain identical across repos
- auth behavior must remain consistent
- transport reconstruction must preserve semantics

---

# 🧠 4. Oramasys Method Applied

## Phase 1 — Context Immersion
Identified cross-repo inconsistencies in:
- endpoint parsing
- scheme reconstruction
- auth token persistence

## Phase 2 — Root Cause Extraction
Moved beyond CodeRabbit symptoms to identify:
- semantic transport identity loss
- stdlib exception leakage
- cross-layer trust boundary violations

## Phase 3 — Architecture Fix
Introduced:
- deterministic validation boundary
- scheme-preserving transport layer
- CI-enforced invariants

## Phase 4 — System Crystallization
System now enforces:
> security is a boundary property, not a per-module concern

---

# 📦 5. Artifacts Produced

- CI Security Guard (GitHub Actions)
- Cursor Agent Execution Manifest (v2 Part 2)
- Scheme preservation contract test
- Auth secure token writer
- Portal XSS hardening patch
- SSRF v2 execution roadmap updates

---

# 🧩 6. Final System Invariant

> No external input can reach execution, storage, or rendering layers without passing through a deterministic, versioned security boundary.

---

# 📌 7. Lessons Learned

- Parser-level assumptions (urlparse safety) are a major hidden risk surface
- Scheme identity must be preserved as a first-class transport property
- CI must enforce security invariants, not just validate correctness
- Cross-repo drift is a primary failure mode in agent-based systems

---

# 🧠 End State
This session transitions Perpetua-Tools into a:
- CI-enforced security boundary system
- cross-repo invariant architecture
- deterministic SSRF-safe execution environment
