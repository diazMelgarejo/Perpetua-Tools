# Session chronicle: Windows dual-monarchy launch fixes, durable peer TLS and stack landing (2026-10-25)

**Author:** claude-opus-5-5 (Claude Code, actor `win-claude-code`, session label "Migrate project
data to corporate account", identity_verified=false). Additive to
`SESSION_CHRONICLE_2026-10-25_E1C2_CLOSEOUT_HANDOFF_LANES_AND_TAKEOVER.md`,
`SESSION_CHRONICLE_2026-10-25_FAST_EXCEPTION_GATE_PARITY_AND_NEXT_STEPS.md` and the review
session's `SESSION_CHRONICLE_2026-10-25_WINDOWS_LAUNCH_TRACK_REVIEW_AND_PEER_PROVENANCE.md`
(diazMelgarejo/Perpetua-Tools#465); none of them is edited.
**Status:** record only; it merges, ratifies and activates nothing. No secrets, keys, tokens,
network addresses, host names, account identifiers, emails or workstation paths. Repositories by
public `owner/repo`, commits by SHA.

## 1. Scope

The operator asked this session to start and debug the PT + orama "dual monarchy" on the Windows
RTX 3080 node (LM Studio local), make `platform/windows/start.ps1` see the Mac and other Windows
nodes, and fix every defect found while running: Sonnet 5.5 (medium) implementers in fresh
worktrees from main, independent review, merge, restart from main. Later asks added a secure
Mac/Windows link (Track B), one harmonized plan, coordination on the GossipBus board with agent ID
envelopes, Codex's recommendations, 100% docstrings on touched files, and this memory.

## 2. Findings from live runs (Track A)

| Id | Defect | Fix landed in |
| --- | --- | --- |
| F1 | `install.ps1` core `pip install` under ErrorActionPreference Stop: pip's stderr notice became a terminating NativeCommandError | diazMelgarejo/orama-system#447 |
| F2/F11 | Half-built orama venv never healed; PT venv installed orama (pip ran from the launcher's directory and PT's requirements file is `-e .`), so PT died on a missing import | #447 |
| F4/F8/F21/F23 | Duplicate `.paths.ps1` write; `load-local.ps1` cut quoted values at `#` and overrode per-invocation env; stale version fallback; read-only modes (`--stop`, `--status`) ran the mesh-secret gate | #447 |
| F3/F6/F9/F14/F15/F25 | Sibling probe fell back to this host (false "2 UP"); self-identification needed an exact IP match (stale config after a DHCP change); `localhost` cost about 2 s (IPv6 first) so the local GPU showed DOWN; `Invoke-LanPeerProbe` returned an array that was always truthy, so failed probes flushed the outbox | diazMelgarejo/orama-system#444 |
| F12/F13 | Discovery on Windows labelled any LM Studio hit as the Mac (a second Windows node could be mislabelled forever via the last-good back-fill); PT's hardware policy shadowed by orama's `utils` package | diazMelgarejo/orama-system#449 |
| F5/F10/F17/F18/F22 | Service logs stopped when the launcher exited (pumped inside its PowerShell); `Wait-ForPort` polled 75 s after the service died; exit 0 with PT dead; "all tiers verified" printed unconditionally; lm-link watcher died with the launcher | diazMelgarejo/orama-system#450 (detached spawn via `scripts/lib/spawn_detached.py`) |
| F20 | PT `/health` 7.76 s: six backend probes in series, public internet on every call | diazMelgarejo/Perpetua-Tools#467 (bounded concurrent probes, cloud-only single-flight cache): about 1.05 s live |
| Guard | Pre-push hook could not launch a shebang script on Windows (WinError 193) | orama #442 `58a0da01`, PT #466 `e86fabc4` (guard sync) |
| P1 | ai-cli-mcp readiness is a hard startup gate, contrary to "everything else optional" | Not changed: owner decision. Runs used the documented skip variable. |

## 3. Track B: durable peer TLS

| Step | Result |
| --- | --- |
| Mac CA trust | Operator gave the CA SHA-256 out of band; the downloaded public CA matched. Trust stayed **process-scoped** (`SSL_CERT_FILE`, later `PEER_CA_FILE` per request). The operator explicitly asked for system-wide trust; the agent declined because changing the OS trust store is a system security setting the operator must make. |
| Windows to Mac | TLS health 200, unauthenticated inbox 401, authenticated list OK; the two E1/C2 receipts and one canary delivered (portal `ok:true`); streaming gossip `ws-peer` PASS over wss. Mac-side independent receipts were still pending when this was written. |
| Security incident | main's `probe_lan_peer.py` hardcoded `http://` for the status check, so one bearer candidate went in cleartext to the Mac's TLS-only port (the TLS server answered 400). Fixed by orama #446 `35d596fc` (https when TLS is enabled, refuse tokens over http). Token rotation on both hosts is an open operator decision. |
| Windows TLS front end | PT #468: `orchestrator/portal_tls_proxy.py` on top of the generalised AlphaClaw proxy, CA mode (`lan_control_plane_pki.py`): local CA (pathlen 0), 30-day serverAuth leaf reissued on SAN change or expiry, CA pin (exit 3 on a different CA), WebSocket pass-through. orama #450 launches it when `PORTAL_TLS_ENABLED=1` and forces the Portal to loopback. |
| Peer trust and delivery | orama #451: `peer_tls.py` (PEER_CA_FILE / pinned fingerprints, token never sent on a trust error), outbox states queued / sent / delivered with content-hash evidence, `outbox-status`, `outbox-resolve`, `outbox-resubmit` (explicit selection, never a bulk retarget). |
| Live evidence (integrated build) | All four services UP, launcher exit 0; Portal listens on loopback only (a LAN connect is refused); https health 200 verified against the Windows CA; unauthenticated inbox 401; a system-roots negative control fails with CERTIFICATE_VERIFY_FAILED; leaf SAN covers loopback and the current LAN address; restarting only the TLS proxy took 22 s and left the other services untouched. |
| CA store relocation | The first live run created the Windows CA inside an MSIX package's redirected AppData (the agent host is a packaged desktop app). An ordinary terminal could not see it and would have minted a second CA. Fixed in PT `fb605dec`: the store defaults to `~/.local/share/oramasys/lan-control-plane` on every OS (the Mac's layout); the existing store was moved whole, fingerprint unchanged, private-key ACLs explicit and not inherited. |

Not proven at time of writing: Mac-to-Windows delivery (needs the operator's out-of-band
comparison of the Windows CA hash, then a canary and an independent receipt each way).

## 4. Board and inbox synthesis (agent ID envelopes)

Envelope fields: author, actor, identity_verified, endorsement, takeover. No entry below is
identity-verified.

| Board ids | Author / actor | Gist |
| --- | --- | --- |
| #36-#42 | win-claude-coder1, win-claude-coder2, win-claude-code; assignment author codex-reviewer-20261021 | E1/C2 jobs: F3 qualification blocked on Windows (POSIX-only private store); evidence lane DONE; receipts sent to the Mac. |
| #44-#64 | win-antigravity (endorsement independent-review) | Harmonization claim, PR #441 opened, Gemini subagents started duplicate PR1-PR5 builds and committed inside this session's worktrees; "274 tests passed" claim. |
| #46, #49, #52, #58 | win-claude-code (this session) | Plan-file ownership, dedup request, urgent stop: peer commits appeared in this session's worktrees; the stray edit was saved as a patch and the worktree restored. |
| #65-#68 | win-claude-code (both sessions) | Provenance corrections by git object id: which commits each agent authored; the peer's test claim not reproduced; the PR4 peer-originated lines identified. |
| #66, #67 | win-claude-code (this session) | Synthesis of the Mac handoff with Track B; the security incident above. |
| #74, #76 | win-claude-code | Decision debt table; restack status (operator restack auto-closed #445, reopened as #449). |
| #77 | id win-claude-code, author unconfirmed | A Windows TLS progress note describing a Caddy/winget attempt that neither Claude session made; authorship query posted (#84). |
| #79 | win-codex | Six recommendations: role-based binds, startup resilience and a Portal-only restart, local-only reproducible TLS, validation gates, canary before outbox reconciliation, focused tests. |
| #80, #82 | win-claude-code (review session) | Lane ownership: this session owns a-*/b-* branches, the merge order and the canary step; broadcast relayed to the Mac inbox over TLS (Mac receipt pending). |
| #84, #85 | win-claude-code (this session) | Merge order with Codex alignment point by point; then MERGED: the operator landed the stack in that order. |

Local LAN inbox: 84 historical files; three since 2026-10-23, one of them a win-antigravity
progress note with empty source/topic metadata (a provenance gap: it cannot be routed by topic).
Local outbox: nine `queued` items. Two are the E1/C2 receipts already delivered over HTTPS under the
verified path and are to be resolved item by item with `outbox-resolve`; seven historical items
stay queued by the Mac's instruction (no bulk retarget). Eight older Windows-sourced items also
appeared in the Mac inbox from an unknown sender; that question is still open on the board.

## 5. Landing

Order posted on the board (#84) and followed by the operator between 09:24Z and 09:30Z, all merge
commits: PT #467 `166b91bf`, PT #468 `ac4bbf03`; orama #441 `d4490725`, #449 `8d213d49`, #447
`646bea8e`, #444 `58e49853`, #450 `41d62d19`, #451 `07944029`. PT went first because orama #450
launches PT's proxy. Follow-ups (one PR per repo off the new main): 100% docstrings and
comment-based help on every touched file, the Codex launcher items (no Portal LAN bind under TLS
mode, a denied User PATH write is a warning, `--restart-portal`, a TLS self-check gate via
`portal_tls_proxy --self-check`) and a `lan_peer_assign.py receipt` command.

## 6. Gotchas worth keeping

* A process started from an MSIX-packaged app writes `%LOCALAPPDATA%` into the package's private
  store. Shared state must live outside AppData; verify with a process launched outside the
  package (for example through WMI `Win32_Process.Create`).
* A PowerShell function returns every uncaptured output: probe stdout plus `$false` is a truthy
  array. Capture native output and return a scalar.
* `localhost` on Windows tries IPv6 first (about 2 s here); probe IPv4 loopback with short timeouts.
* Under ErrorActionPreference Stop with redirection, native stderr is a terminating error in
  PowerShell 5.1. Wrap native calls with Continue and check `$LASTEXITCODE` instead.
* A venv `python.exe` on Windows is a launcher; the listener is its child in a kill-on-close job.
  PID files hold the launcher; port ownership shows the child.
* NTFS directory listings can show 0 bytes for a log another process holds open; open the file to
  read its real length.
* `pip install -r <other repo>/requirements.txt` containing `-e .` installs the current directory,
  not the other repo.
* Deleting a stacked PR's base branch after merge auto-closes the PRs on top; merge without
  deleting and retarget.
* Two sessions posting under one agent id make the board unattributable by id; include a session
  label in every note and ask authors to confirm rather than assume.
* A health check alone never proves inbox delivery: evidence ladder is TLS health 200, protected
  401, authenticated call, then an independent receipt from the receiver.

## 7. Open work, by owner

* Operator: compare the Windows CA hash with the Mac out of band; rotate the control-plane token on
  both hosts in one step; DHCP reservations or DNS names for the nodes (T1); decide a fleet CA with
  name constraints (T4); decide the ai-cli-mcp gate (P1); update the two rewound PT submodule
  checkouts; shut down the Mac's temporary public download listener; say who sent the eight old
  items and who wrote board #77.
* win-claude-code (this session): land the follow-up PRs, restart from main in fresh worktrees,
  run the Mac canary and receipt round trip, resolve the two delivered outbox items.
* Mac lane: start.sh parity (fail-fast, honest fallback status), load-local.sh `#` handling,
  independent receipts for the Windows deliveries.
* Not done: no token changes, no trust-store changes, no bulk outbox retarget, no system services.
