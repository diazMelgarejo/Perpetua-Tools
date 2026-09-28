# Portal facade audit and swarm fixes — 2026-09-28

Session record for the Orama Knowledge Portal / swarm-approval facade audit
against Perpetua-Tools. Knowledge search, MCP, and A2A stay in orama-system.

## What we decided

- Perpetua is the durable job authority and a co-install compatibility shim.
  It is not the place for the read-only knowledge gateway.
- A first draft (Perpetua-Tools #404) added `POST /models/route` and hoisted
  swarm identity out of job `metadata`. It was closed during a V1 re-audit,
  then reopened on the same branch `cursor/portal-facade-route-jobs-3c54`
  at the operator's request. Still a draft. Not merged.
- Orama portal bugs were fixed on `cursor/portal-swarm-approval-fixes-3c54`
  in orama-system (commit `2a3ce316`).

## Perpetua-Tools #404

- `POST /models/route` accepts the portal JSON and returns `backend_hint` /
  `model_hint`. `GET /models/route` still returns `fallback_chain`.
- `POST /v1/jobs` copies `role`, `specialization`, `session_id`,
  `parent_orchestrator_id`, and `artifact_policy` from `metadata`, and
  accepts the same fields at the top level (top-level wins).
- `task_type` is taken from the body or from `constraints`.
- Focused check: `python3 -m pytest tests/test_portal_facade_route.py -q`
  (6 passed).

## Orama portal fixes

- Launch dispatches the cached approved preview. It no longer rebuilds
  assignments (that minted a second token and 422'd on routing flicker).
- Live hardware policy is rechecked at launch.
- Job submit sends top-level `role`, `specialization`, `session_id`,
  `parent_orchestrator_id`, `artifact_policy`, and `task_type`, plus
  `metadata.model` from `model_hint`. `backend_hint` of `auto` is omitted.
- Route failures are recorded as `routing_error` instead of a silent empty
  route.
- `ORAMA_SWARM_LEGACY_APPROVE` defaults off. Issuing an approval without a
  secret fails closed.
- Perpetua checkout resolution checks `PERPETUA_TOOLS_ROOT`,
  `PERPETUA_TOOLS_PATH`, and `PERPETUATOOLSROOT`, then a sibling
  `Perpetua-Tools` tree, then the historical `perplexity-api/Perpetua-Tools`
  path.
- Spawn affinity uses Windows when the agent name contains `win`.
- Browser launch sends `preview_id` and `approval_token`. Launch stays
  disabled when hardware policy is missing. The unreachable-state hint says
  port 8002. Vite's node config no longer depends on a missing `@types/node`.
- Checks: `tests/test_swarm_launch.py`, `tests/test_swarm_approval.py`,
  and `tests/test_portal_mutating_route_auth.py`.
