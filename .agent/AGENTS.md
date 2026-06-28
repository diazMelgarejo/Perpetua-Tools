# Agent Infrastructure

This folder is the portable brain. Any harness (Claude Code, Cursor, Windsurf,
OpenCode, OpenClaw, Hermes, standalone Python) can mount it and get the
same memory, skills, and protocols.

## Memory (read in this order)
- `memory/personal/PREFERENCES.md` — stable user conventions
- `memory/working/WORKSPACE.md` — current task state
- `memory/working/REVIEW_QUEUE.md` — pending candidate lessons waiting for you
- `memory/semantic/DECISIONS.md` — past architectural choices
- `memory/semantic/LESSONS.md` — distilled patterns (rendered from `lessons.jsonl`)
- `memory/episodic/AGENT_LEARNINGS.jsonl` — raw experience log (top-k by salience)

## Review Queue (host-agent responsibility)

Candidate lessons are clustered + staged automatically by `memory/auto_dream.py`.
The host agent — you — does the actual review using the CLI tools below.

Check `memory/working/REVIEW_QUEUE.md` at session start. If pending > 10 or
oldest staged > 7 days, review before substantive work.

Workflow:
1. `python .agent/tools/list_candidates.py` — pending candidates, sorted by priority
2. For each: decide accept / reject / defer based on claim, evidence_ids,
   cluster_size, and any contradictions with existing LESSONS.md
3. `python .agent/tools/graduate.py <id> --rationale "..."` to accept
4. `python .agent/tools/reject.py <id> --reason "..."` to reject
5. `python .agent/tools/reopen.py <id>` to requeue

## Skills
- `skills/_index.md`
- `skills/_manifest.jsonl`
- Load SKILL.md only when triggers match task

## Protocols
- `protocols/permissions.md`
- `protocols/delegation.md`

## Security Invariant Enforcement Protocol (OramaSys v2)

This section defines the **authoritative security enforcement contract** for all agent execution environments.

It is derived from the OramaSys v2 security architecture and MUST be enforced in conjunction with:
- `docs/v2/plans/security-v2-roadmap.md` (system architecture)
- `docs/v2/plans/security-v2-roadmap-part2.md` (execution layer)
- `.github/workflows/security-invariant-enforcer.yml` (CI enforcement bot)
- `SECURITY.md` (repository security policy)

---

## 🧠 Core Invariants

All agent actions MUST obey the following invariants:

### 1. SSRF Safety Boundary
- All URL inputs MUST pass through `endpoint_policy_core`
- Raw `urlparse()` usage in production paths is forbidden
- Private, loopback, and metadata IPs MUST be blocked deterministically

### 2. Auth Safety Boundary
- Control plane tokens MUST be written using secure file primitives only
- Token files MUST be created with `0600` permissions at creation time
- No token material may appear in logs, HTML, or UI rendering

### 3. Transport Identity Integrity
- URL scheme (`http/https`) MUST be preserved end-to-end
- Reconstruction layers MUST NOT hardcode transport schemes
- Any downgrade or implicit normalization is a critical violation

### 4. Rendering Safety
- All external inputs MUST be HTML escaped before rendering
- No raw event/model metadata may reach UI layers

### 5. Cross-Repo Consistency
- Orama-system and Perpetua-Tools MUST implement identical security rules
- Divergence in SSRF/auth/transport logic is forbidden

---

## ⚙️ CI Enforcement Binding

The following CI pipeline enforces these invariants:

👉 `.github/workflows/security-invariant-enforcer.yml`

It MUST:
- Block PRs containing `urlparse(` usage
- Block token leakage patterns (`ORAMA_CONTROL_PLANE_TOKEN`)
- Detect unsafe transport downgrades (`http://http` patterns)
- Run full test suite before merge

---

## 🔗 Security Policy Reference

Refer to:
- `SECURITY.md` for repository-level security rules
- v2 roadmap for architectural guarantees

---

## 🚨 Failure Semantics

Violations are classified as:

- **HARD BLOCK**: SSRF bypass, auth leakage, scheme downgrade
- **CI FAILURE**: lint/security invariant violation
- **ARCHITECTURAL DRIFT**: cross-repo mismatch in behavior

---

## 🧩 Operational Rule

> If a fix cannot be verified against these invariants, it MUST NOT be merged.

All agent reasoning must defer to this protocol as the final authority layer.
