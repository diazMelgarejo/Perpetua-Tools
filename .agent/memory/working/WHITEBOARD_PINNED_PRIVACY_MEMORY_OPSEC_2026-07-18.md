# WhiteBoard Pinned Message - Portable Memory, OpSec, and SecOps

Date: 2026-07-18
Scope: PT PR #260 and future OramaSys v2 / multirepo agent memory work

## Pinned Rule

Portable agent memory is a security boundary. Treat it like source code that may
be copied across machines, repos, forks, PRs, review tools, and future agents.

Tracked files may name sensitive **categories** only:
- private identity literals
- private or unclassified email addresses
- credentials and API keys
- device addresses and local endpoints
- workstation topology
- temp-worktree topology
- local path fragments

Tracked files must not contain the concrete values for those categories. Exact
private values live in an off-repo, local-only registry and are loaded by guards
at runtime.

## Operational Invariants

- A negative rule must not leak the literal it is trying to ban.
- Supersession is not sanitization. A rendered lesson, replacement note, or new
  summary does not clean the older source row that produced it.
- Scan the whole `.agent` surface: episodic JSONL, semantic JSONL, candidates,
  working notes, protocols, skills, rendered views, and generated summaries.
- Report guard findings by category, file, and line. Do not print the matched
  secret or private literal.
- Prefer the strictest current guard as the multirepo standard for OramaSys v2.
- Before ending a privacy/security session, close the loop: scan, test, commit,
  push, fetch, verify branch state, and inventory dirty worktrees.

## What Changed Today

- PT's `.agent` guard now treats `.agent/` as a first-class privacy scan target.
- Concrete local topology fragments are loaded from a local-only registry rather
  than hardcoded in tracked guard source.
- PT memory now records the source-row vs rendered-view distinction explicitly.
- Orama v2 now has a canonical portable-memory topology invariant document.
- The coordination board carries a critical whiteboard item so offline agents
  can rediscover the rule when they come back online.

## Cross-Repo Pointers

- PT: `.agent/memory/semantic/DOMAIN_KNOWLEDGE.md`
- PT: `.agent/memory/semantic/LESSONS.md`
- PT: `scripts/review/repo_hygiene.py`
- Orama: `docs/v2/47-portable-memory-local-topology-invariant.md`
- Orama: `bin/orama-system/skills/oramasys-method/SKILL.md`

