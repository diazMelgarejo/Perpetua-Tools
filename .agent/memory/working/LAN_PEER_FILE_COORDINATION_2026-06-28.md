# LAN peer file coordination — lessons landmark (2026-06-28)

**Status:** accepted into PT memory  
**Secrets:** never store `ORAMA_CONTROL_PLANE_TOKEN` in this tree  
**SSOT (orama):** `bin/orama-system/skills/hermes-harness/references/lan-peer-self-talk.md` section F

## What shipped (orama `6fa3dd9`+)

| Component | Path / endpoint |
|-----------|-----------------|
| File inbox | openclaw state `lan_peer/inbox/` (local only, never commit) |
| CLI | `bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py` |
| HTTP API | `POST /api/peer-file`, `GET /api/peer-inbox`, `GET /api/peer-inbox/{name}` |
| Fan-out manifests | `references/autoresearch-fanout-example.json`, `self-improve-fanout-2026-06-28.json`, `code-sections-fanout-2026-06-28.json` |
| Mac playbook | `references/mac-co-orchestrator-playbook.md` |
| Win handoff | `references/co-orchestrator-handoff.md` |

## Lessons (crystallized)

### L1 — File inbox beats WS for assignments

- **Fact:** Markdown drops via `POST /api/peer-file`; peers read with `list --peer` / `read --peer --name`.
- **Pattern:** Fan-out JSON splits by `assignee` (`mac` | `win`); local keeps file, remote POSTs to peer portal.
- **Rationale:** WS/SSE for heartbeat/probe only; hypotheses, code-review, self-improve travel as plain files.

### L2 — CLI flag order (`>= 9f89051`)

- **Fact:** `--peer` is on the **subcommand**: `drop --peer`, `list --peer`, `read --peer`.
- **Wrong:** `lan_peer_assign.py --peer drop` (parent-parser era).

### L3 — Repo root for local inbox import

- **Fact:** `_SCRIPT_DIR.parents[4]` is orama repo root (not `parents[5]`).
- **Symptom:** `ModuleNotFoundError: orama_system` on local `fanout` drop.

### L4 — Partial fan-out success

- **Fact:** One peer drop can fail (404 pre-pull, auth) while local assignments succeed.
- **Pattern:** `fanout` returns `status: partial`, exit code 1, continues per item.

### L5 — Bidirectional peer-file unblock

- **Fact:** Mac `HTTP 404 /api/peer-file` means portal predates `86c90bc` or needs restart.
- **Fix:** `git pull --ff-only origin main` then `./start.sh --stop && ./start.sh --lan-peer --no-open`.
- **Bug fix:** `/events/peer-stream` needs `response_class=StreamingResponse` or OpenAPI generation crashes portal.

### L6 — Co-orchestration model

- **Fact:** Hermes/Codex/cursor-agent do **not** run on the peer host over HTTP.
- **Pattern:** Split topics per host; each machine runs local PATH agents; reply via `drop --peer`.

### L7 — Post-commit sync discipline

- **Pattern:** After every review and commit: `git fetch --prune`, `git pull --rebase origin main`, `git push origin main`, confirm `HEAD == origin/main`.

## Auth modes (joint-account, no token values)

| Mode | When |
|------|------|
| `joint` | PT `.state/control_plane_token` differs from orama token; either lane unlocks both |
| `orama_only` | Single shared `ORAMA_CONTROL_PLANE_TOKEN` on both hosts (steady state) |
| `pt_only` | PT lane only |

Probe reports `auth_mode` in `last_lan_peer_probe.json`.

## Fan-out IDs in flight (2026-06-28)

| ID | Mac task | Win task |
|----|----------|----------|
| `2026-06-28-autoresearch-001` | hypothesis | GPU run + read `hypothesis-summary.md` |
| `2026-06-28-self-improve-001` | lessons draft | runtime lessons |
| `2026-06-28-code-sections-001` | `lan_peer_*` stack review | `autoresearch_bridge.py` review |
| `2026-06-28-coord-playbook` | pull playbook | staged `mac-read-co-orchestrator-playbook.md` on Win inbox |
