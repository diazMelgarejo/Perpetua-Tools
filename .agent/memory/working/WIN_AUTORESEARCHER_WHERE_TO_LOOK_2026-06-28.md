# Win autoresearcher — where to look (READ FIRST)

**Agent:** `autoresearcher`, win-researcher — **Hermes-only** Win subagents + cursor-agent  
**Platform:** Windows Hermes harness; Mac peer uses **OpenClaw** (not Hermes)  
**Date:** 2026-06-28

## Your assignment

1. Read Mac hypothesis from **peer inbox** (not git, not WS stream).
2. Run GPU benchmarks on Win 27B stack per hypothesis priority.
3. Drop `gpu-results.md` back to **Mac peer inbox**.

## Step 1 — read Mac hypothesis

```powershell
cd $env:ORAMA_SYSTEM_PATH
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py read --peer --name hypothesis-summary.md
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py read --peer --name win-gpu.md
```

Fallback tracked copy: `bin/orama-system/skills/hermes-harness/references/results/hypothesis-summary.md` (after `git pull`).

## Step 2 — GPU execution (PT L2)

| What | Where |
|------|-------|
| Autoresearch bridge | `Perpetua-Tools/orchestrator/autoresearch_bridge.py` |
| Preflight routes | `orchestrator/control_plane.py` |
| Routing | `config/routing.yml` (autoresearch routes, `affinity: win-rtx3080`) |
| Tests | `tests/test_autoresearch_bridge.py` |
| Win 27B endpoint | `last_discovery.json` -> `endpoints.win` (never hardcode IP) |
| LM Studio | `http://localhost:1234/v1` on Win |

```powershell
# Stack must be up
.\platform\windows\start.ps1 --lan-peer --no-open
python bin\orama-system\skills\hermes-harness\scripts\probe_lan_peer.py --json
# peer-lmstudio PASS required before GPU dispatch
```

## Step 3 — drop results to Mac

```powershell
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py drop --peer `
  --file .\results\gpu-results.md `
  --assignee mac --topic autoresearch/gpu-done `
  --fanout-id 2026-06-28-autoresearch-001
```

Mac reads: `lan_peer_assign.py list` (local inbox, no `--peer`).

## Code-review sibling task

Also assigned: `code-review-win-autoresearch.md` in Win local inbox (from fan-out `2026-06-28-code-sections-001`).

Review `autoresearch_bridge.py` + routing; drop `win-code-review.md` to Mac when done.

## PT memory cards

| File | Purpose |
|------|---------|
| `.agent/memory/working/WIN_AUTORESEARCHER_WHERE_TO_LOOK_2026-06-28.md` | **This card** |
| `.agent/memory/working/LAN_PEER_FILE_COORDINATION_2026-06-28.md` | File inbox lessons |
| `.agent/memory/semantic/DOMAIN_KNOWLEDGE.md` | LAN peer + routing sticky notes |

## Playbook cross-links (orama)

- `references/mac-co-orchestrator-playbook.md` section 4 (Win cursor-agent)
- `references/autoresearch-win-gpu.md` (assignment template)
- `references/autoresearch-fanout-example.json` (manifest)

## Hypotheses to benchmark (from Mac)

| ID | Claim | Falsify if |
|----|-------|------------|
| H1 | File inbox beats WS for fan-out | peer-file fails >20% on LAN |
| H2 | Joint auth stable for bidirectional drops | 401 after discovery refresh |
| H3 | Win 27B faster than Mac 9B for coding loop | Win GPU + file round-trip slower |

Include wall-clock timings per hypothesis in `gpu-results.md`.
