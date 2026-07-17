# Phase Board Fragmentation — Root Cause Analysis

Date: 2026-07-17
Repository: `diazMelgarejo/Perpetua-Tools`
Branch: `fix/gossip-db-canonical-resolution-20260717` (PR #256)
Status: fixed by Codex (`9642ae24`), this doc records the investigation and the discarded hypotheses so the debugging path isn't re-walked next time.

## Symptom

`python3 scripts/agent_coordination.py phase list` crashed on any non-`Phase-N.M`-shaped phase name:

```
ValueError: could not convert string to float: 'StateTransitionManager-Integration'
```

## The confusing part

A test already existed that claimed to cover exactly this — `test_phase_list_handles_nonnumeric_phase_names` — and it **passed**. Running the same scenario as a standalone script crashed reliably, every time, byte-identical source file. Same repo, same commit, two different invocation paths, two different outcomes. That contradiction is what made this worth writing up: several plausible-looking explanations were checked and ruled out before finding the real one.

## Hypotheses checked and discarded

1. **Stale bytecode cache.** Cleared every `__pycache__` under `scripts/`, `tests/`, and repo root. No change — still crashed standalone, still passed under pytest.
2. **A stale installed copy in `.venv/site-packages` shadowing the live source** (a pattern that *did* explain an unrelated file, `check_dep_pins.py`, earlier this session). Checked — no such copy exists for `agent_coordination_core.py`.
3. **`sorted()` skips calling `key()` for a 1-element list**, so the crash-prone branch never executes when only one phase exists. Directly falsified with a 3-line repro: `sorted(['a'], key=bad_key)` still calls `bad_key`. Python always computes keys up front regardless of list length.
4. **A conftest.py fixture or exception handler swallowing the error.** Read `tests/conftest.py` in full — nothing there touches `_phase_list`, no broad exception handling, no locale/warning filters relevant to this.
5. **Duplicate test definition, pytest silently picking the wrong one.** Grepped the whole repo for the test's name — one definition, one call site.

## The real cause

`_phase_list` / its sort-key helper existed **three times**, one per coordination module:

- `scripts/agent_coordination_core.py` — the buggy version (`return (0, float(name))` with no guard on the fallback branch)
- `scripts/agent_coordination_legacy.py` — same bug, independently
- `scripts/agent_coordination.py` (the CLI-facing facade) — **already fixed**, with a documented rationale for the tuple-of-ints approach (it even calls out a second, subtler bug the naive fix avoids: encoding a minor version as a float breaks ordering past two digits — `Phase-2.10` would sort before `Phase-2.9`)

The facade module assigns `_phase_list = _impl._phase_list` near the top (aliasing the legacy implementation), then **redefines `_phase_list` locally further down the file** — the later definition wins, so the module's actual exported `_phase_list` is the good one.

But the real CLI entry point (`scripts/agent_coordination.py`'s `__main__` block) calls `main()`, which is imported from `agent_coordination_core.py` — and `_amain()` inside *that* module resolves `_phase_list` from its own module globals, not the facade's. So the live CLI path always ran the buggy core implementation, regardless of the correct one sitting unused two files away.

The existing test imported `_phase_list` from the facade module (`scripts.agent_coordination`) — which resolved to the good, unused implementation. The test was real, it ran, it passed — it just wasn't exercising the code path a user actually hits.

## Why this matters beyond one crash

This is a specific instance of a pattern this session kept surfacing in different forms (the gossip DB path resolution fix earlier on this same branch is another): **a fix landing in one of several duplicate/fragmented implementations doesn't help unless every caller actually reaches it.** A green test suite can coexist with a broken CLI when the thing under test and the thing users invoke have quietly drifted into two different functions with the same name.

## Fix

Codex applied the facade's already-correct tuple-of-ints sort key to `agent_coordination_core.py` and `agent_coordination_legacy.py` (commit `9642ae24`), so all three implementations now agree, plus added direct regression coverage in `tests/test_agent_coordination_phases.py` that imports from `agent_coordination_core` specifically (not the facade), so a future regression in the module the CLI actually runs would be caught directly rather than incidentally.

**Not done as part of this fix, worth a follow-up:** true de-duplication — one canonical `phase_sort_key`, with `agent_coordination.py` and `agent_coordination_legacy.py` importing it rather than each carrying their own copy. Three copies fixed consistently today; nothing stops a fourth divergence next time someone touches sort behavior in only one of them.

## Verification

```
python3 scripts/agent_coordination.py phase list   # no longer crashes, prints correctly
uv run --offline python -m pytest tests/test_agent_coordination.py tests/test_agent_coordination_phases.py tests/test_gossip_bus.py -v
# 58 passed
```
