# Coordinated cycle 005 — sequential Win jobs + PT learn

**Date:** 2026-06-28  
**Fan-out:** `2026-06-28-coord-005`  
**v1 anchor:** `orama-system/docs/plans/2026-05-29-03-v1.1-definitive.md` §2 frugality tiers  
**Status:** autoresearcher CLOSED; coder awaiting Mac card

## This round

| Step | Job | Status |
|------|-----|--------|
| 1 | Win autoresearcher — finalize H5 cross-host | **done** (`gpu-results-h5-final.md` -> Mac) |
| 2 | Win coder — bridge PR verify | **pending** (Mac sends card separately) |

## H5 result

Mac 3/3 @ 1/4/5 itp (490s) vs Win 3/3 @ 1/1/1 (280s). Win wins itp and wall.

## Joint learn

Both hosts: `learn.py` + `auto_dream.py` after deliverables land.  
Win summary: `win-self-improve-cycle-005.md` (orama results).

## Queue

`win_job_queue.py` idle both roles. Run `enqueue` after Mac drops next `win-coder-*` card.
