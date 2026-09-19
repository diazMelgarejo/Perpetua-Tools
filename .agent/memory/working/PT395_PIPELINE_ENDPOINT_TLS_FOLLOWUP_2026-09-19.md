# PT #395 follow-up — TLS bearer hops and Orama PR #363 peer ref

**Date:** 2026-09-19 UTC
**Branch:** `fix/pt-pipeline-endpoint-tls-20260917`
**PR:** Perpetua-Tools #395 (existing; no second PR)

## Published state

| Item | SHA / ref |
| --- | --- |
| Pre-follow-up remote tip | `d751f2aa669feaffde0a26c43fef7a7b3fd4a72f` |
| Security + mapping follow-up | `84cd350d4c83ce5a194c33c7f451ddf6b6a8df97` |
| Orama PR #363 head | `refs/pull/363/head` (= `bb3eb7dac66196d14f938237cfa8da5ccbe56ebe`) |
| Equivalent Orama branch | `cursor/tiered-pipeline-runtime-fb76` |
| Missing (do not use) | `pr-363` (404 on `diazMelgarejo/orama-system`) |

## Included from the unpublished `b4189236` envelope

- Bearer HTTPS-only `url_checker` on remote `ssrf_request` hops
- Packaged host policy: no `startswith("127.")` hostname exception
- Matching tests
- Stack-aware CI resolver (not bare `github.head_ref`)
- Graduated candidate `b7d7be187d74` plus append-only episodic / `LESSONS.md` / `lessons.jsonl` rows (byte-identical to the mail patch)

## Intentional deltas vs that envelope

- Peer mapping is `refs/pull/363/head` (tracks the open Orama PR)
- Equivalent live branch name is recorded in `orama_system_peer_equivalents`
- `scripts/hooks/check_memory_records.py` derives ids with `cluster.pattern_id` so `learn.py`-minted candidates pass the memory gate
- This chronicle and `docs/LESSONS.md` session line

## CI wiring (job 105865624057)

The resolve step wrote a quoted PT branch into `GITHUB_OUTPUT` (`\"$GITHUB_HEAD_REF\"` inside an already-quoted `echo`), so checkout fetched `refs/heads/"fix/pt-pipeline-endpoint-tls-20260917"` on orama-system, failed, and `continue-on-error` greenwashed a `main` fallback. Parity then compared PT tip against orama `main`.

Checkout now uses `peer_ref` from `--github-output`. While Orama PR #363 is open, that is `cursor/tiered-pipeline-runtime-fb76` (`refs/pull/363/head` remains an equivalent). After #363 merges, resolve returns `main` as the declared peer. Declared checkout failure fails the job; `main` fallback is only for unmapped same-named-ref attempts.

## Publish rules still in force

Ordinary non-force fast-forward only. No merge, no second PR, no history rewrite.
