# PT closure handoff — 2026-11-06

Canonical register: Orama repository,
`docs/v2/MASTER-CLOSURE-AND-IMPLEMENTATION-PLAN-2026-11-06.md`.
That register owns C0–C12 and D1–D3. This file is a repository entrypoint;
do not create a second checklist or interpret draft recommendations as ratified.

Publication is held until the user confirms existing PRs merged and releases
the push hold. Reconcile the local plan commits with actual merged content first.

PT owns manual compatibility characterization in C2 and privacy/concurrency
work in C4/C5. D1 explicitly keeps PT manual: do not add a scheduled cleanup or
maintenance daemon. Automatic expiry/release is owned by Oramasys v2. Entry points:
`orchestrator/coordination/liveness.py`, `claims.py`, `task_queue.py`, `paths.py`
and `cli.py`. The August draft's `heartbeat.py` API is not an existing API.

The draft path/name/hash identifier leaks topology. Prefer random identifiers
with a protected local mapping. Retain compatibility shims until their removal
is explicitly decided; a repository search cannot enumerate external callers.

Ratified 2026-11-06: D1 v2-only automatic expiry/release with fencing; PT stays
manual. D2 retain shims and decide removal later. D3 qualify both POSIX and
native Windows before promotion. Preserve native memory source bytes. The
merge barrier and push hold still apply.
