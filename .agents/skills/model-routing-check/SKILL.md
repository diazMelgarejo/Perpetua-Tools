---
name: model-routing-check
description: Verify LM Studio endpoint reachability, hardware affinity, and routing table validity before any agent dispatch
user-invocable: false
---

Before dispatching any agent:

## 1. Endpoint reachability

1. Check Mac: `curl -s --connect-timeout 3 [REDACTED]/models | python3 -c "import sys,json; print('Mac OK:', len(json.load(sys.stdin)['data']), 'models')"`
2. Check Win: `curl -s --connect-timeout 3 "$LM_STUDIO_WIN_ENDPOINTS/v1/models" | python3 -c "import sys,json; print('Win OK:', len(json.load(sys.stdin)['data']), 'models')"`

## 2. Hardware affinity gate (required)

LM Studio mirrors Win models on Mac's `/v1/models` — list membership is **not** proof a model is safe on Mac.

```bash
cd "$(git rev-parse --show-toplevel)"
python scripts/hardware_policy_cli.py --check-openclaw
# Or full startup gate:
# cd ../orama-system && ./start.sh --hardware-policy
```

Must pass before dispatch. See `.claude/skills/hardware-policy/SKILL.md` for NEVER_MAC / alias rules.

## 3. Routing table

3. Cross-check `config/routing.yml` task_types against `config/models.yml` role assignments

## 4. Degraded operation

4. If either endpoint is down: log warning, continue with available endpoint only. Do NOT abort reachability checks silently — but affinity violations are **fail-closed**.

## 5. Report

5. Report: which endpoints are live, affinity check result, which task_types are fully routable
