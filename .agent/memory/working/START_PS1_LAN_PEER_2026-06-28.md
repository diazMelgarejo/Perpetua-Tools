# Windows start.ps1 + LAN peer — 2026-06-28

**Status:** Fixed on orama-system `main` (`2717eee`) · **Verified:** 2026-06-28 — `start.ps1 --no-open` exit 0; ports 8000/8001/8002 UP  
**Playbook:** `orama-system/.../references/lan-peer-self-talk.md#operator-playbook`

## Failures observed (pre-fix)

| Command | Failure |
|---------|---------|
| `start.ps1 --no-open` | Parameter `--no-open` not found |
| `start.ps1 --status` | `PID` is read-only (assigned to `$pid`) |
| `start.ps1 --stop` | Same `$pid` bug — never killed listeners |
| Start path | Wrong uvicorn modules; `Contains()` on env dict |

## Win operator sequence (post-fix)

```powershell
cd $env:ORAMA_SYSTEM_PATH
git pull --ff-only origin main
$env:PERPETUA_TOOLS_PATH = "<your PT clone>"

.\platform\windows\start.ps1 --stop
.\platform\windows\start.ps1 --no-open
.\platform\windows\start.ps1 --status   # expect 8000/8001/8002 UP

# LAN peer (after .env.local bind + shared token on both hosts):
.\platform\windows\start.ps1 --lan-peer --no-open
python bin\orama-system\skills\hermes-harness\scripts\probe_lan_peer.py --json
```

Hermes: `/lan-peer-self-talk`
