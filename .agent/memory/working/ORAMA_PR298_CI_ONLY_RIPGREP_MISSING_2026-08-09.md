# orama-system PR #298: CI-only test failure — root cause was missing ripgrep

Date: 2026-08-09
Branch: `fix/mapfile-to-while-read` (orama-system, worked in a disposable local clone)
Final state: all PR #298 CI checks green (test, test 3.11/3.12/3.13, git-hygiene,
lint, build, aguara scanner, CodeQL, gitleaks).

## Symptom

`tests/test_scan_tracked_banned_tokens.py::test_key_name_collision_rejects_non_key_name_occurrence`
and `::test_internal_bootstrap_files_still_fail_on_other_banned_values` failed
**only** on GitHub Actions `ubuntu-latest`, with:

```text
AssertionError: rc=0 stdout='OK: no banned tokens in tracked files\n' stderr=''
```

Passed identically on: my Mac, a codex sandbox run, and a full 1500+-test local
suite run. This pattern (CI-only, clean local repro across 3 environments) is
what made ambient-environment contamination look like the obvious answer.

## False lead: environment-isolation hardening (did NOT fix it)

First hypothesis: `_run_scan()`'s `os.environ.copy() + one override` inherited
the real ambient `$HOME`/`$PATH`, so results could depend on whatever exists on
the running machine. Hardened to a minimal, fully explicit `env` dict (`PATH`,
isolated `HOME`, `OPENCLAW_ATTRIBUTION_PATTERNS` only). Pushed, and — critically
— **verified against the actual next CI run's log**, not assumed fixed. The
identical failure recurred, with the enhanced assertion message confirming the
hardened code path had genuinely run. This disproved the hypothesis instead of
re-claiming success on a plausible-but-unverified fix. See
[[feedback_verify_before_replaying_past_agent_work]] for the general version of
"don't trust a fix until the actual downstream system confirms it."

## Real diagnosis: bash -x trace + targeted rg instrumentation

Added a diagnostic-only re-run: whenever `_run_scan()` unexpectedly got
`rc==0`, re-run the scanner under `bash -x` and stash the trace on the result
object so the next CI failure would surface it directly instead of requiring
another guess-and-push round trip. Pushed, read the actual CI log's captured
trace. It showed:

```text
++ rg -F -i -n -- <redacted-local-only-key-name> scripts/cursor/seed-banned-attribution-patterns.sh
++ true
```

`rg` ran and matched nothing, even though the fixture file demonstrably
contained the literal token. The scanner's own `rg ... 2>/dev/null || true`
suppresses whatever `rg` would have said about *why*. Added a second, more
targeted diagnostic: call `rg` directly (no `2>/dev/null` suppression) plus
`rg --debug`, `rg --no-ignore`, `rg --version`, and dump the raw file bytes.

That round's CI log gave the real answer directly, via Python's own
`subprocess.run(["rg", ...])` raising (not the shell-suppressed version):

```text
FileNotFoundError: [Errno 2] No such file or directory: 'rg'
```

**ripgrep was never installed on the runner.** Neither `test.yml`'s `test` job
nor `ci.yml`'s `test` matrix (3.11/3.12/3.13) had an install step for it — the
assumption that `ubuntu-latest` ships ripgrep preinstalled was wrong (or at
least not true for this runner image).

## Why this matters beyond the test file

`scripts/git/scan-tracked-banned-tokens.sh`'s core loop is:

```bash
done < <(rg -F -i -n -- "$token" "$rel" 2>/dev/null || true)
```

When `rg` is missing, bash's "command not found" is redirected to
`/dev/null`, `|| true` catches the nonzero exit, the process substitution
yields zero lines, the scan loop body never runs, `errors` stays 0, and the
script prints `OK: no banned tokens in tracked files` — a **false-clean
result indistinguishable from a genuinely clean scan**. This is the general
bug class: any `external-tool ... 2>/dev/null || true` inside a scan/check
loop treats "tool missing" identically to "tool ran, found nothing." A
security-relevant scanner must never let a missing dependency produce the
same output as a clean pass.

## Second landmine found mid-fix: the CI placeholder pattern was a real word

`ci.yml`'s `git-hygiene` job runs this same scanner for real, against
`ci-bootstrap-private-attribution.sh`'s CI-only pattern file. That script's
own comments (dated 2026-08-08, CodeRabbit review 4890233271) already
document that this consumer is **intentionally inert in CI by design** — the
real banned-token registry is local-only per
[[feedback_portable_memory_security_boundary]] / orama
`docs/v2/47-portable-memory-local-topology-invariant.md`, never present in
CI, and failing closed there was already considered and rejected once.

The placeholder token used was the literal word `REDACTED` — which
legitimately appears throughout real security/redaction docs and code
(`grep -rli REDACTED .` found 20+ genuine tracked-file hits). Installing
ripgrep in `git-hygiene` (needed so the script's new `command -v rg` guard
doesn't hard-fail there) would have made that scan real for the first time
and mass-failed CI on totally unrelated content.

Fix: replaced `REDACTED` with a synthetic sentinel
(`ci-placeholder-pattern` + `-never-matches-real-content-7f3ae9c1`) in both
`ci-bootstrap-private-attribution.sh` and its sibling
`write-openclaw-private-attribution.sh`. First attempt wrote it as one
literal `echo` argument — the scanner then flagged **the scripts' own
source** for containing their own placeholder token (the same class of bug
`SCAN_TRACKED_KEY_NAME_FILES`/`_is_allowed_key_name_collision` already
exists to handle, just for a different literal). Fixed by assembling the
sentinel via string concatenation at runtime
(`_placeholder_token="ci-placeholder-pattern"; _placeholder_token+="-never-matches..."`)
so the literal substring never appears verbatim in tracked source.

## Fixes landed (commit `9da99e4e` and prior diagnostic commits on the branch)

1. `scripts/git/scan-tracked-banned-tokens.sh`: `command -v rg` guard at the
   top — exits 1 with a clear error if `rg` is missing, instead of silently
   scanning nothing.
2. `.github/workflows/test.yml`, `.github/workflows/ci.yml`: install
   ripgrep (`sudo apt-get install -y ripgrep`) in every job that runs this
   test suite or the real scanner (`test`, `test` matrix, `git-hygiene`).
3. `ci-bootstrap-private-attribution.sh`, `write-openclaw-private-attribution.sh`:
   placeholder token changed from `REDACTED` to a concatenation-built
   synthetic sentinel.
4. `tests/test_scan_tracked_banned_tokens.py`: removed the diagnostic
   scaffolding once root cause was confirmed; added a permanent regression
   test (`test_fails_loudly_when_ripgrep_is_missing`) that strips the `rg`
   binary's directory from `PATH` and asserts the scanner now fails loudly
   instead of reporting clean.

Verified: full local simulation of the exact CI bootstrap+scan sequence
against a clean isolated `$HOME` exits 0 genuinely (not silently); all 4
tests in the target file pass with real ripgrep in `PATH`; every job on PR
\#298 (`test`, `test (3.11/3.12/3.13)`, `git-hygiene`, `lint`, `build`,
`aguara` scanner, `CodeQL`, `gitleaks`) passed for real on the actual CI run
that included these commits.

## Gold-nugget lesson

See graduated lesson `lesson_90fcf80b1355` in `LESSONS.md`: a `tool ...
2>/dev/null || true` pattern inside any scan/check loop must be guarded with
an explicit `command -v tool` dependency check, and a "fix" for a CI-only
failure is not confirmed until the *next actual CI run* — not local
reproduction, not sandboxed reproduction, not a plausible hypothesis —
confirms it, ideally via real captured execution evidence (a `bash -x`
trace, direct tool invocation bypassing the script's own error
suppression) rather than another round of guessing.
