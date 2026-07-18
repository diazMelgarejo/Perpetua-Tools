# Agent Infrastructure

This folder is the portable brain. Any harness (Claude Code, Cursor, Windsurf,
OpenCode, OpenClaw, Hermes, standalone Python) can mount it and get the
same memory, skills, and protocols.

## Rules

1. Edit first, commit later - Make changes, AskUserQuestion if they're correct, commit if YES; no question or no answer is NOT a yes.
2. Commit first, push later - Only push when everything is verified by the user and final. If unsure, use a disposable worktree.
3. READ this first: https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/SKILL.md

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
- `protocols/path-hygiene.md` — **anti-doxxing / LINT-006** (always apply)

## Path Hygiene (anti-doxxing — always apply)

**Never** write workstation-specific paths into git-tracked files — including
`.agent/memory/*`, lessons, review queue summaries, skills, and docs.

| Do | Don't |
|----|-------|
| Repo-relative paths (`../../Perpetua-Tools/.agent`) | `OS-specific home-directory paths`, `OS-specific home-directory path form` |
| Env anchors (`$REPO_ROOT`, `PERPETUA_TOOLS_ROOT`) | workspace-tree paths |
| Generic `~/.gstack/projects/<slug>/` | Pinning "canonical workspace" paths in memory |
| `orama-system` / `Perpetua-Tools` repo names | Teaching agents your Downloads folder layout |

**Write boundaries:** all memory writers call `sanitize_tracked_path_leaks()` from
`memory/path_hygiene.py` (`learn.py`, `graduate.py`, `review_state.py`, episodic hooks).

**Antipattern:** Graduating or echoing lessons that treat a personal Downloads path as
canonical — reject those candidates; use repo names + env vars instead.

Full contract: `protocols/path-hygiene.md` · lessons `lesson_da04cbbae68b`, `lesson_456ea361526d`, `lesson_6fc89e22e3bb`.

## Post-review micro-remediation (sister pattern to the one below)

When addressing review findings on an ALREADY-OPEN PR (as opposed to merging
independent branches): freeze main as a write target, cluster findings by
root cause and fix the abstraction once, keep commits cohesive by failure
class, and on any post-merge problem prefer a safety-ref-protected ancestry
reset over accumulating revert commits.

**Canonical doctrine (orama-way):**
[orama `post-review-micro-remediation.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/references/post-review-micro-remediation.md)
— 6 phases: Freeze → Root-cause clustering → Branch discipline → Integration
(safety ref before reset) → Verification (fixed/superseded/documented, never
silent) → Closure. This section is the portable-brain summary; the reference
doc is authoritative.

## Multi-agent merge conflict protocol

When merging nested branches produced by independent agents against a moving main, follow this protocol exactly. **Never guess conflict resolution.**

**Canonical doctrine (orama-way):** load **oramasys-method** →
[orama `integrative-merge.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/oramasys-method/references/integrative-merge.md)
(synthesize, never amputate; six resolution modes). This section is the portable-brain summary; the skill reference is authoritative.

**Board-job source line:** before claiming write work from GossipBus / job board
rows, verify the row has `source_ref` and `expected_base_sha`; create a fresh
worktree from that exact source and stop if `HEAD` differs. Same board plus same
repo is not enough. See `references/branch-local-review-remediation.md`.

### Step-by-step

1. **Simulate first — touch nothing.**
   ```bash
   git merge --no-commit --no-ff <branch>
   git diff --name-only --diff-filter=U   # enumerate ALL conflicts
   git merge --abort
   ```

2. **Present every conflict to the human** with both sides shown. One question per file. Wait for explicit direction before proceeding.

3. **Human-directed resolution strategies:**
   - `additive` — one side is empty, other has content → take the content side
   - `union` — both sides have partial content → concatenate (ours first, theirs appended)
   - `superset` — one is a structural superset of the other → verify all rows from the smaller are in the larger, then take the superset
   - `synthesize` — both sides changed the same region for valid different reasons → blend both (e.g. new API + old branch's tests)
   - `architecturally-correct` — one side has a bug the other fixes → take the correct side regardless of branch origin
   - `api-correct` — casing/type mismatch → take the API-correct form

4. **Resolve all conflicts in one pass** using the directed strategy. Never delete content — archive/quarantine if something must be removed.

5. **Verify before committing:**
   ```bash
   python3 -m pytest -q
   python3 scripts/review/repo_hygiene.py .
   git diff --name-only --diff-filter=U  # must be empty
   ```

6. **Push → wait for CI → perform GitHub API merge.**

7. **Wait 10 minutes between sequential merges.** Before merge N+1, confirm `mergeable_state: clean` via GitHub API.

### Key invariants

- "Merged" on GitHub ≠ content is on the target branch. Always verify with `git diff origin/main...origin/<branch>` after any merge.
- CodeRabbit re-scans on every push and creates new comment threads. Run the post-merge sweep after every merge, not just once.
- JSONL memory files (lessons.jsonl, AGENT_LEARNINGS.jsonl): dedup by `id` / `run_id` after union — keep the **first** occurrence per id.
- LESSONS.md is rendered from lessons.jsonl — never hand-edit it directly (AGENTS.md Rule 5). Always go through `graduate.py`.

## Host-agent CLI tools (in `tools/`)
Daily driver, highest-leverage first:
- `recall.py "<intent>"` — surface graduated lessons relevant to what
  you're about to do. **Run before deploy / migration / timestamp / debug /
  refactor work.** This is how lessons cross harnesses.
- `learn.py "<rule>" --rationale "<why>"` — teach the agent a new lesson
  in one shot (stage + graduate + render). For rules you already know.
- `show.py` — one-screen dashboard of brain state: episodes, candidates,
  lessons, failing skills, activity graph.
- `list_candidates.py` / `graduate.py` / `reject.py` / `reopen.py` — review
  protocol for patterns the dream cycle has staged.
- `memory_reflect.py <skill> <action> <outcome>` — log a significant event.

## Rules
1. Check memory before decisions you have been corrected on before.
2. If `REVIEW_QUEUE.md` shows backlog past threshold, handle it before the new task.
3. Log every significant action to `memory/episodic/AGENT_LEARNINGS.jsonl`
   via `.agent/tools/memory_reflect.py`.
4. Update `memory/working/WORKSPACE.md` as you work; archive on completion.
5. Never hand-edit `memory/semantic/LESSONS.md` — it's rendered from
   `lessons.jsonl`. Use `graduate.py` / `reject.py` instead.
6. Continue using and committing `.agent/memory/**` through the established
   memory tools when the work requires it, but never record the owner's Gmail
   address in memory files, CONTRIBUTING.md, or PR templates; use a neutral
   owner-identity label instead.
7. Follow `protocols/permissions.md`. Blocked means blocked.
8. When a self-rewrite hook fires, propose conservative edits only.
9. The harness is dumb on purpose. Reasoning lives in skills + the host agent.

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
