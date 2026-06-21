# Major Decisions

> Record architectural or workflow choices that would be costly to re-debate.
> Use this template for each entry:

## YYYY-MM-DD: Decision title
**Decision:** _what was chosen_
**Rationale:** _why, in one or two sentences_
**Alternatives considered:** _what else was on the table and why rejected_
**Status:** active | revisited | superseded

## 2026-01-01: Four-layer memory separation
**Decision:** Split memory into working / episodic / semantic / personal rather than one flat folder.
**Rationale:** Each layer has different retention and retrieval needs. Flat memory breaks at ~6 weeks.
**Alternatives considered:** Flat directory (fails at scale), vector store (over-engineered for single user).
**Status:** active

## 2026-06-21: perpetua-core salvage port confirmed complete; push gate is hardware review

**Decision:** `oramasys/perpetua-core` salvage translation RC-1 is done — all 16 tasks committed, 73 tests green across 3 repos (`perpetua-core` 56, `oramasys` 5, `Perpetua-Tools` 12). The only remaining gate before merging `feat/salvage-plugins-rc1` → `perpetua-core` main is user end-to-end hardware review on Mac Ollama (`localhost:11434`) + Win LM Studio (`192.168.254.103:1234`). This is per the Push Policy in PROGRESS.md.

**Rationale:** PROGRESS.md at `oramasys/perpetua-core` HEAD (`56f2a6d`) shows every row `DONE`. All spec invariants verified in code: `PerpetuaState(BaseModel)`, `scratchpad: dict[str, Any]`, Python ≥3.11, engine 102 lines (≤80 soft cap exceeded by compile path — acceptable), `set_entry` + `compile` present, all 6 plugin ports landed (`tool_node`, `routing`, `validator`, `interrupt_guard`, `parallel`, `message`). Hypothesis property tests landed in `tests/property/`. Discovery layer ported verbatim from v1.

**Alternatives considered:** Treat as blocked / in-progress. Rejected — PROGRESS.md explicitly states "DONE march" with commit SHAs for every row.

**Status:** active

**Links:**
- Repo: https://github.com/oramasys/perpetua-core
- Spec: https://github.com/diazMelgarejo/orama-system/blob/main/docs/superpowers/specs/2026-05-17-salvage-translation-design.md
- Plan: `orama-system/docs/superpowers/plans/2026-05-17-salvage-translation-v1-discovery.md`
- PROGRESS.md: https://github.com/oramasys/perpetua-core/blob/feat/salvage-plugins-rc1/PROGRESS.md
