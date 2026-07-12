# 07. Multi-Agent Collaboration — Version Registry, Scope Claims, Test Isolation

**TL;DR:** Two agents working simultaneously on overlapping files will diverge. Scope claims, additive-only changes, and the version registry prevent this.

---

## What Broke (2026-04-12)

1. **Stash pop after rebase** — another agent pushed "PT-first orchestrator migration" while our stash was waiting. `git stash pop` produced add/add conflicts on every file we touched. `alphaclaw_bootstrap.py` got both versions appended; required Python line-by-line surgery.

2. **Hardcoded LAN IP broke CI** — `/health` defaults changed to `<YOUR_LAN_IP>` (real LAN IP) in `fastapi_app.py` → broke `test_health_uses_plain_string_defaults` on all CI machines.

3. **Test module state contamination** — `importlib.reload(bridge)` + monkeypatch without restore leaked `AUTORESEARCH_DEFAULT_BRANCH = "dev"` into downstream tests.

---

## Version Registry — All PT Canonical Locations

**Current version: `0.9.9.7`.** Do NOT bump without explicit user instruction.

| File | Field |
|------|-------|
| `pyproject.toml:12` | `version = "0.9.9.7"` |
| `orchestrator/__init__.py:5` | `__version__ = "0.9.9.7"` |
| `orchestrator/fastapi_app.py:74` | `version="0.9.9.7"` |
| `orchestrator/fastapi_app.py:295` | `"version": "0.9.9.7"` (health JSON) |
| `orchestrator.py:97` | `VERSION = "0.9.9.7"` |
| `config/devices.yml:6` | `version: "0.9.9.7"` |
| `config/models.yml:6` | `version: "0.9.9.7"` |
| `SKILL.md:3` | `**Version:** \`v0.9.9.7\`` |
| `README.md:1,170` | `v0.9.9.7` |

---

## Multi-Agent Synchronization Protocol

1. **Read `docs/LESSONS.md` first** — scope claims are written here
2. **Scope claim** — append `## [IN PROGRESS] YYYY-MM-DD — <name> — <topic>` to LESSONS.md before touching files; replace with final header when done
3. **Additive changes** — append to files over rewriting; conflicts only happen when both agents edit the same lines
4. **Commit body names changed constants/APIs** — it's the only async channel between agents
5. **Never hardcode LAN IPs in source defaults** — `127.0.0.1` in code, real IPs in `.env` only
6. **Test isolation** — `autouse` fixture that restores module-level state after `importlib.reload()`

---

## Pre-Commit Checklist

```bash
# 1. Sync with what other agents pushed
git fetch origin main
git log --oneline HEAD..origin/main

# 2. No LAN IPs in source defaults
grep -rn "192\.168\." --include="*.py" | grep -v "test_\|#\|LESSONS\|\.env"

# 3. Tests pass
python -m pytest -q
```

---

## Orphan Branch Recovery

```bash
# Symptoms: git merge-base HEAD origin/main exits 1
# git rebase origin/main produces add/add conflicts on every file

# Fix:
git fetch origin main
git reset --hard origin/main
# Re-apply your changed files manually from /tmp backup
```

Prevention: always create feature branches from `origin/main`:
```bash
git checkout -b feature/xyz origin/main
```

---

## Rules

1. **Scope claim before touching files** — write `[IN PROGRESS]` marker to LESSONS.md
2. **Source defaults must be loopback** — `127.0.0.1`, not real LAN IPs
3. **`autouse` fixture restores module-level state** after every test that uses `importlib.reload()`
4. **Always branch from `origin/main`** — never detached HEAD or agent-created branch

---

## Commits
- `71a15f7` (PT) — fix(health): restore 127.0.0.1 loopback defaults for ollama/lm_studio_host

## Intra-Machine Agent Coordination (added 2026-07-11)

Two Claude Code sessions (this one and a concurrent one in
`.claude/worktrees/phase-1-impl`) worked the same repo simultaneously this
session — one on Phase 0/PR review, the other autonomously implementing
Phase 1.0–1.3.1 and Phase 2/4 of the self-healing-mesh plan. Collision was
avoided only by manually reading `git log`, `ps aux`, and uncommitted
`git status` before every dispatch — expensive and error-prone. Fixed with
`scripts/agent_coordination.py`, which reuses the EXISTING
`orchestrator/GossipBus` (SQLite FTS5 event log, already intra-machine —
zero LAN dependency) as a claim/registration board, instead of building new
infrastructure:

```bash
# once per session:
python3 scripts/agent_coordination.py register <agent_id> <agent_type> <model> "<notes>"
# before starting work on a named task/gap:
python3 scripts/agent_coordination.py list                    # check for open claims
python3 scripts/agent_coordination.py claim <agent_id> <task> "<notes>"
# when done:
python3 scripts/agent_coordination.py release <agent_id> <task>
```

Works correctly from any git worktree of the repo with zero new env vars —
resolves the shared db path via `git rev-parse --git-common-dir` (every
worktree of the same repo answers with the same path). Claims/registration
are advisory only (a warning, never a hard block) — this is coordination
for human-supervised concurrent agent sessions, not a distributed lock.

Rule going forward: **before dispatching a new agent (kimi, cline,
antigravity, or a Claude Code subagent) onto a named task, run `list` first
and `claim` before it starts** — cheaper than re-deriving collision state
from git archaeology every time.

## Related

- [Session log 2026-04-12](../LESSONS.md#2026-04-12--claude--48-hour-multi-agent-sprint-collaboration-patterns--version-registry)
- [UTS/06-multi-agent-collab.md](https://github.com/diazMelgarejo/orama-system/blob/main/docs/wiki/06-multi-agent-collab.md)
- `scripts/agent_coordination.py` — intra-machine claim board (this repo)
