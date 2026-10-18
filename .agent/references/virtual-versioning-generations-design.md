# Virtual versioning for oramasys (pointer)

Canonical design, pending merge in
[orama-system PR #417](https://github.com/diazMelgarejo/orama-system/blob/docs/m1-virtual-versioning-design-20261018/docs/v2/references/m1-virtual-versioning-generations-design-2026-10-18.md):
`m1-virtual-versioning-generations-design-2026-10-18.md`. Decisions and designs live there; this
file only points and summarizes.

Summary: rollback as a move between immutable generations, modelled on browser compatibility
modes, not a repository revert or a package downgrade.

- A generation is an immutable folder of pins, manifest, coverage, registry reference, approval,
  evidence digests, receipt and a sunset rule. One canonical inventory with content digests; a
  later change creates a new generation.
- One reviewed `ACTIVE` pointer names the live generation. Undeclared production, CI and
  installer consumers refuse; they never silently follow `ACTIVE`.
- Retirement is forbidden while a generation is active or declared. A rollback is a reviewed
  pointer-transition receipt, not a generation state.
- Pins decide only what a fresh install gets. Every claim states its fidelity: `declared`,
  `verified-installed` or `reproduced`.
- Where pins live decides how real the rollback is: Option A (pointer as a check) or Option B
  (install-time constraints file). Option A comes first; Option B is a separate G2b path.
- Status: G0 approved by the operator on 2026-10-18; only G1 (data-only migration of the gen-1
  and gen-2 evidence into generation folders) is authorized.
