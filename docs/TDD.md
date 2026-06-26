# TDD — Test-Driven Development (POINTER)

> ⚠️ **POINTER — canonical content lives in orama-system.**
> Do not duplicate checklists here; edit the canonical doc only.

| Artifact | Canonical location |
|----------|-------------------|
| Prescriptive gate (pre-code, pre-commit, Vite gap) | [orama-system `docs/TDD.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/TDD.md) |
| v2 policy (outsourced review, autoresearcher loop) | [orama-system `docs/v2/26-tdd-and-outsourced-review-doctrine.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/26-tdd-and-outsourced-review-doctrine.md) → local pointer [`docs/adr/ADR-004-tdd-and-outsourced-review-doctrine.md`](adr/ADR-004-tdd-and-outsourced-review-doctrine.md) |
| Anti-patterns | [orama-system `docs/testing-anti-patterns.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/testing-anti-patterns.md) |
| Agent skill (executable) | `vendor/ecc-tools/skills/tdd-workflow/SKILL.md` |
| oramasys-method Stage 4 gate | orama-system `bin/orama-system/skills/oramasys-method/references/tdd-gate.md` |

## Local test commands

| Surface | Command |
|---------|---------|
| Python / orchestrator | `pytest` (see repo `pyproject.toml` / CI) |
| AlphaClaw / packages | `npm test` in package root |
| Operator console (orama `web/`) | `cd ../orama-system/web && pnpm test` |

Before any production code change: follow the **Pre-Code-Change Checklist** in canonical `docs/TDD.md`.
