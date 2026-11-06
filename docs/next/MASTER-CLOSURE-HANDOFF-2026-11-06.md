# PT closure handoff — 2026-11-06

Canonical register: Orama repository,
`docs/v2/MASTER-CLOSURE-AND-IMPLEMENTATION-PLAN-2026-11-06.md`.
That register owns C0–C12 and D1–D3. This file is a repository entrypoint;
do not create a second checklist or interpret draft recommendations as ratified.

Publication is held until the user confirms existing PRs merged and releases
the push hold. Reconcile the local plan commits with actual merged content first.

PT owns C2–C5: characterize current cleanup and CLI semantics, then implement
only the ratified maintenance, identity and concurrency scope. Entry points:
`orchestrator/coordination/liveness.py`, `claims.py`, `task_queue.py`, `paths.py`
and `cli.py`. The August draft's `heartbeat.py` API is not an existing API.

The draft path/name/hash identifier leaks topology. Prefer random identifiers
with a protected local mapping. Retain compatibility shims until their removal
is explicitly decided; a repository search cannot enumerate external callers.

Current decision state: D1 daemon authority, D2 deprecation/removal and D3 target
platform remain pending user answers. Existing manual behavior is not changed
by this planning commit. Preserve native episodic/semantic memory source bytes.
