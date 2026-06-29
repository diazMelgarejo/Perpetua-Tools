# Coordinated cycles 016–018 — reset-on-job listen

**Fan-out:** `2026-06-29-coord-016-018`

| Cycle | Job | Status |
|-------|-----|--------|
| **016** | PT #199 merge ack + 53/53 Mac verify | **done** |
| **017** | G1 baseline partial (tests pass, harness gap) | **done** |
| **018** | L1 ingredients ack (P5 gate) + listen scripts | **done** |
| Listen | 3×15m `job_cycle_listen.sh` (reset on job_done) | **background** |

## Listen semantics

`coord_mark_job_done.sh` after each job. `job_cycle_listen.sh` waits 900s from **last** job finish; new job resets the window.
