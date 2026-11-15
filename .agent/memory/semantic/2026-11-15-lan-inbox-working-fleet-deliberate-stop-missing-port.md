# 2026-11-15 Lan inbox: a working fleet, a deliberate stop, and the missing port

The inbox is a file drawer, not a chat log. Read in order, it is one story:
a working two-host fleet, a deliberate stop, two quiet months, and a return
that keeps tripping over the same missing port.

This card is the coordination story. The Windows C6 qualification is the
other card, `2026-11-15-c6-windows-owner-rights-native-ntfs-evidence.md`.
The local gossip board and this drawer are two boards. A note on one is not
a note on the other.

## 2026-06-28 The drawer opens

The Mac drops a co-orchestrator playbook, an autoresearch hypothesis sheet,
and a note that `POST /api/peer-file` finally returns 200. The claim they
want tested is small and practical: a markdown file beats a WebSocket stream
for handing work across the LAN, joint auth can survive ten drops without a
401, and the Windows 27B box might finish a coding loop faster than the
Mac's 9B even after the file round-trip. Windows answers the same evening
with GPU notes and a self-improve report. The Mac then sits in a 15-minute
warmup, polling its inbox every five minutes. Coordination is the inbox.
There is no remote agent call.

## 2026-07-03 The wire is up

A handoff says the probe is clean on portal health, portal status, the model
server, and the peer socket. The coder and autoresearcher queues are empty,
and Windows is waiting for a real task on the 27B model. Through the middle
of the month the drops are self-improve cycles, frugality reruns, and Hermes
harness work. It looks like a shop in operation.

## 2026-07-23 The operator stops the monitors

The operator ends the session in writing. `OramaCoordPulse` is disabled. The
Mac is told to unload the scheduled monitors and not delete them. Coders
should not expect pulse dispatches. That note is an operator rule, not a
crash report. The local board still carries it. Do not re-enable those
monitors unless the operator asks.

## 2026-07-27 The last fleet ceremony

Mac first, then the Windows boxes. Harmonize the gossip secret, back up
before the mesh pull request, and do not put that secret in chat or git.
After that the inbox thins out.

## 2026-08 The drawer thins

Two notes, both local. On the 6th the Hermes envelope work has landed in
four commits and the push is deferred behind an operator gate. On the 23rd
a Mac broadcast says an SSRF split-identity fix is implemented and verified,
and not yet committed. September is absent from the drawer. The monitors
stay paused. When someone looks again, the standing instruction from 23 July
is still the last order. Local work on one host continued through those
months. The cross-host drawer did not.

## 2026-10-23 The resumption names itself

A Windows agent registers on the local gossip board, points at the canonical
gossip skill on main, and says the job is to inspect about four months and
roughly two thousand commits of drift since July. The same note repeats that
the coordination monitors are still paused.

## 2026-10-25 The fleet comes back as a review machine

Seven E1/C2 pull requests are open, clean, and unmerged. The operator
merges. Claude on the Mac is about to run out of budget and hands the
Windows peers a resume order: SQLite qualification, an evidence-parity
review, no merges, no hardcoded addresses, one owner per branch. The 27th
is a canary day: pulses, TLS proofs, a round that ends with the Mac saying
port 8443 is online again. Trust notes say both drops landed. The work is
closeout, not a new hypothesis.

## 2026-11-07 The same failure returns

The Mac says its launcher is back: the three plain ports and the TLS front
end, under a user job, with automatic flush still disabled. It asks Windows
to retry one named receipt and not to bulk-flush. On the 10th the Mac writes
the diagnosis that this host later repeated. After a plain stack restart,
ports 8000 and 8001 answer, 8002 is on loopback, and 8443 has no listener.
Health checks never looked at 8443. The front end is started by hand. A
plain launch is taught to start the front end when one is provisioned. On
the 11th the Mac's consolidated note says the silent period had a second
cause too: an orphan portal had written fifteen files into a scratch inbox,
and those fifteen were recovered byte for byte. Promotion of the repos is
refused. Gates are the operator's.

## 2026-11-12 A quiet drawer

A lessons fix, a C6 phase note, a PowerShell 5.1 encoding question. Not a
fleet day.

## 2026-11-15 This host's missing listener

The other host's outbox was still 78 delivered, 6 superseded, and 9 queued.
Those nine were no longer a bad certificate pin. Nothing here was listening
on 8443, so the files never arrived. A small Windows gossip snapshot in the
inbox lists six local models and a queue depth of 320. The services were
brought back up, including the TLS front end. The nine files stay on the
other host until that host retries them.

## Rules a later agent should reuse

- A drop is delivered only when that drop's own result has `ok` true,
  `received_at`, and a byte count equal to the file. Portal acceptance is
  not storage. An outbox state word is not a receipt. A local sidecar is
  this host's store record. Content-verified delivery also needs a matching
  receiver digest.
- Startup is ready only when the TLS front end is listening with the other
  services. The plain portal stays on loopback. The model server and the
  portal are separate listeners.
- Discovery is discover, save, try, then mark stale. Ports 11434 and 1234
  are defaults. Save the port that answered.
- A remote call is a v2 controller effect. The envelope header stays in
  perpetua-core. The oramasys controller commits the claim, the lease, and
  the redacted outbox together. Telos dials pinned TLS. Phylax admits the
  caller. Agate cannot authorize. Gossip replicates the event after commit
  and cannot claim or complete the work. If the mesh is off, the inbox drop
  is the whole call.
