# Session chronicle: re-establishing contact among the grandfathered fleet, technical record (2026-10-24 to 2026-10-26)

**Author:** claude-opus-5-5 (Claude Code, actor `win-claude-code`, session label "Migrate project
data to corporate account", identity_verified=false). Additive to
`SESSION_CHRONICLE_2026-10-25_WINDOWS_DUAL_MONARCHY_LAUNCH_FIXES_AND_PEER_TLS.md` and the review
session's chronicle (diazMelgarejo/Perpetua-Tools#465); neither is edited. Reference material:
`LAN_PEER_TLS_AND_DELIVERY_DOMAIN_KNOWLEDGE_2026-10-26.md`.
**Status:** record only; it merges, ratifies and activates nothing. No secrets, keys, tokens,
network addresses, host names, account identifiers, emails or workstation paths.

## 1. State at the start

The Windows node and the Mac node had stopped exchanging files. The Mac had moved its Portal to a
TLS front end (private CA, 30-day leaf) and refused plain HTTP; the Windows outbox held nine
records whose stored destination was still the old plain-HTTP port, and the Windows node had a new
DHCP address. Windows had no TLS front end at all, so nothing could be delivered to it
authenticated. The Mac instance asked the operator to "enable the existing TLS proxy or provide a
secure portal URL" for Windows.

## 2. Timeline (UTC dates; evidence level in the last column)

| Step | Action | Evidence |
| --- | --- | --- |
| 1 | Operator gave the Mac CA SHA-256 in a separate message; the downloaded public CA matched. Trust kept per process (`SSL_CERT_FILE`). Operator asked for system-wide trust; declined as a system security setting and offered the process-scoped path. | hash equal |
| 2 | Verified: Mac TLS health 200, protected inbox 401, authenticated inbox list 200, system-roots negative control fails (`CERTIFICATE_VERIFY_FAILED`). | TLS + auth |
| 3 | Sent only the two E1/C2 receipts, as the operator instructed, over the verified path. Did not flush the other seven queued records. | portal `ok:true`; Mac receipt pending then |
| 4 | Security incident: main's `probe_lan_peer.py` hardcoded `http://` for `/api/status`, so one bearer candidate went in cleartext to the Mac's TLS-only port (the TLS server answered 400). Fixed in orama #446 (scheme from `PEER_PORTAL_TLS_ENABLED`; tokens refused over `http://`). Rotation recommended, not done. | code + tests |
| 5 | Windows to Mac canary accepted (496 bytes); the Mac later issued a receipt with the same filename, byte count and a byte-level SHA-256. `ws-peer` PASS over `wss` proved the streaming channel one way. Caveat: that receipt has no line-ending-normalised hash, so under the delivery rule (normalised content hash equality) it is evidence of receipt of those exact bytes, not a full `delivered` proof. | receiver receipt (byte hash only) |
| 6 | Track A launcher fixes F1-F25 built by Sonnet 5.5 (medium) implementers in disjoint worktrees, each independently reviewed (up to three fix rounds), merged by the operator as a stack. | CI + reviews |
| 7 | Track B: PT `portal_tls_proxy` (CA mode, WebSocket pass-through) and orama peer trust (`peer_tls.py`) plus delivery states, outbox commands. | tests |
| 8 | Integrated build (all branches merged onto main in a scratch worktree) run live: all services up, exit 0, Portal loopback-only, https health 200 against the new Windows CA, 401 unauthenticated, negative control fails. | live |
| 9 | Found the CA store had been created inside the app host's package-redirected AppData; moved to `~/.local/share/oramasys/lan-control-plane` (PT `fb605dec`), fingerprint unchanged, ACLs explicit. TLS proxy restart alone took 22 s. | live |
| 10 | Landed in order PT #467, #468; orama #441, #449, #447, #444, #450, #451; follow-ups consolidated by the review session into orama #452 and PT #465 (one PR per repo). | merged |
| 11 | Restarted from fresh worktrees at main twice: exit 0 in 488 s (cold, includes venv builds) and 33 s (warm); new self-check PASS. | live |
| 12 | Mac published a readiness receipt; Windows verified the Mac TLS again with the Mac CA and sent the public-CA handoff (3,366 bytes, no hash, no credential): portal `ok:true`. | acceptance only |
| 13 | Windows downloaded the Mac's updated handoff ZIP on operator approval; SHA-256 matched the operator's value, no unsafe member paths, manifest verified. | hash equal |

Still unproven when this was written: Mac to Windows delivery (needs the Mac to check the CA
against the fingerprint the operator gave its operator, then send one canary; Windows then
returns filename, received-byte SHA-256 and UTC time), and a Mac-side receipt for the Windows CA
handoff.

### Addendum: reciprocal-link hold (2026-10-26)

The Mac later staged the Windows public-CA handoff for local diagnostic comparison, but the file
did not match the independently supplied fingerprint. No bearer, authenticated request, or
Mac-to-Windows canary was sent. The existing Windows-to-Mac receipt therefore remains one-way
evidence only, not proof of reciprocal delivery. Resumption requires a corrected fingerprint
through an independent operator channel, followed in order by verified TLS health, an
unauthenticated protected-endpoint rejection, one non-sensitive canary, and a receiver receipt
that includes both byte and LF-normalised content hashes. This addendum preserves the earlier
timeline rather than rewriting its historical statements.

## 3. Defects, root causes and fixes (technical)

| Id | Root cause | Fix |
| --- | --- | --- |
| Venv never healed | Gate was `Test-Path python.exe`; a half-built venv passes. PT venv got orama because `pip install -r <PT>/requirements.txt` (`-e .`) ran in the launcher's cwd | Probe third-party imports; run pip with the PT directory as cwd (orama #447) |
| False "2 UP" / "0 UP" | Unknown sibling fell back to localhost; `localhost` cost 2 s so the 2 s probe timed out | Report unknown, no probe; IPv4 loopback with 5 s timeout (#444) |
| Failed probe flushed outbox | `Invoke-LanPeerProbe` returned `@(<stdout>, $false)`, truthy | Capture and return a scalar bool (#444) |
| Logs stopped at launcher exit | Output pumped by `CopyToAsync` inside the launcher's PowerShell | Detached spawn with file-appended stdout (#450) |
| 75 s wait on a dead service | `Wait-ForPort` ignored process exit | Fail fast with log tail; non-zero exit (#450) |
| `/health` 7.76 s | Six probes in series, public internet each call | Concurrent bounded executor, deadline, cloud cache (PT #467) |
| Mac label stuck on a second Windows node | Back-fill of last-good address, scan hit labelled by port alone | Exclude known Windows addresses; evidence tiers (#449) |
| Pre-push hook WinError 193 | Shebang script launched directly | Launch through bash (#442, PT #466) |
| Bearer over http | Hardcoded scheme in status probe | Transport guard (#446) |
| Second CA risk | AppData redirection for packaged processes | Home-relative store (PT `fb605dec`) |
| Self-check false PASS | Any `OSError` counted as refusal; empty probe list passed | Only `ConnectionRefusedError` is proof; otherwise WARN (PT #465) |
| `-WhatIf` said "added" | Summary ignored the switch | Report "would add" (orama #452) |
| `ensure_requirements.ps1` unparsable | BOM-less file with an em dash under 5.1 | Add BOM; add BOM and parse tests for every `.ps1` |
| Test collection errors | `fcntl` imported at module top; two test files with one basename | `msvcrt` fallback; rename |

## 4. Process lessons

* Spawn disjoint file ownership and give each agent its own ports and a scratch profile; two
  agents sharing a worktree produced commits attributed to the wrong author.
* Treat a review-fix as a fix round of the same tier, then re-review; reviews found real defects
  every round (a stale `WIN_IP` trusted, GGUF counted as Windows evidence for an explicit Mac).
* Verify claims independently: a peer's "274 tests passed" was not reproduced and was recorded as
  unreproduced; a doc-only commit is proved by a comment-stripped AST/token comparison, not by
  reading the diff.
* Do the live check in the same context the operator will use. Verifying from a packaged process
  hid the store-location bug until a process launched outside the package was tried.
* One branch and one PR per repository for follow-ups.
* The board is append-only; a leak is handled by an index-aware redaction (delete the old text from
  the FTS index with the exact old values, update, reinsert) after a backup, plus a recorded
  correction. The FTS table is external-content and has no update trigger.

## 5. Open work, by owner

Operator: bearer rotation on both hosts, names or reservations, fleet CA decision, MCP gate
policy, stop the temporary download listener. Mac lane: CA check and canary to Windows, receipts
for the Windows deliveries, `start.sh` parity, `load-local.sh` `#` handling. This session:
reconcile the two delivered outbox records item by item once receipts exist; no bulk retarget.
