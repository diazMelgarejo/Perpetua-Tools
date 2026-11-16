# Fail-Secure Qualification, OWNER RIGHTS, and Transient-Failure Retry - Domain Knowledge (2026-11-15)

Verified reference facts from the PT #514 enforcement work, the oramasys #100 ACL work, and the CI
synthesis ([orama-system PR 516](https://github.com/diazMelgarejo/orama-system/pull/516)).
Author/actor: win-cline-20261115, self-reported.

## Fail-secure configuration loading

- Unavailable security configuration must not become permission. A policy loader that catches a
  read failure and returns None converts a fail-closed gate into fail-open: the reviewer reproduced
  all four catalog candidates being dispatched after a FileNotFoundError or ValueError raised between
  route assembly and the gate.
- Durable shape: load ONE validated snapshot before route assembly, refuse (503) when it cannot be
  obtained, and hand the same snapshot to every consumer (route construction and the gate) through an
  additive keyword-only parameter. Two independent reads of the same security document are a TOCTOU
  window even when both usually succeed.
- Gate-denied candidates must skip their availability probe entirely: a denied Ollama-backed GLM
  cloud candidate reached the one-shot cloud probe when denial and probing were computed in the same
  loop without an early continue.
- Registry reachability flags (ModelTarget.online) are probe inputs, not qualification verdicts;
  conflating them with the catalog online kill switch defeats the probe-failure fallback. Only the
  catalog row online flag is a dispatch kill switch.
- Request schemas must not carry gate-exemption fields: OrchestrateRequest has no dispatch_mode, so
  the qualification_probe exemption is not caller-reachable.

## Windows default-DACL and OWNER RIGHTS

- General rule (corrected 2026-11-16, review 5915346045): a directory created with NULL security
  attributes gets a default security descriptor. It inherits the parent's inheritable ACEs, and only
  when none are inherited does the creator token's default DACL apply
  ([CreateDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createdirectoryw)).
  NULL does not by itself select the token default DACL or block parent inheritance.
- Observation from the tested environment only (Windows 11 26200, Python 3.13.14, C6 harness run of
  2026-11-15): the harness directories showed a protected DACL of SYSTEM, Administrators and OWNER
  RIGHTS (S-1-3-4), with no inherited flags in icacls. That ACE set matches what CPython 3.13+
  applies for `os.mkdir(path, mode=0o700)` on Windows: an explicit protected DACL
  `D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)`
  ([os.mkdir docs](https://docs.python.org/3/library/os.html#os.mkdir), gh-118486), and the C6
  harness creates its attempt roots with `mkdir(mode=0o700)`
  ([benchmark_revocation_availability.py](https://github.com/oramasys/oramasys/blob/main/scripts/benchmark_revocation_availability.py)).
  The original record attributed the result to NULL security attributes; the creation mode is the
  better-supported cause (reviewer inference, 2026-11-16). The parent directory's inheritance state
  was not recorded in the run evidence.
- OWNER RIGHTS (S-1-3-4) is owner-equivalent, not foreign: Windows resolves it to the object owner
  at access-check time, and directory/file ownership is pinned to the current user before the ACL
  check, so an OWNER RIGHTS ACE cannot widen access to any principal the owner check has not
  admitted.
- Elevated runners (GitHub windows-latest) default object ownership to Administrators, not
  TokenUser: native default-DACL assertions must probe _check_windows_ownership on a fresh object and
  skip exactly that environment with a stated reason (mirror the elevated-ownership isolation in
  [tests/windows/test_private_store_native.py](https://github.com/oramasys/oramasys/blob/main/tests/windows/test_private_store_native.py)).
- Native Win32 regressions belong in tests/windows/ (the dedicated windows-private-store workflow
  lane); platform-independent policy rows stay in the application suite so Linux
  compatibility-oracle skip allowances are preserved exactly (the f6295a1 pattern).

## Transient CI failure retry (the census method)

- One real failure (PyPI IncompleteRead on the agent-audit job) produced three fragments on three
  branches. Classify the failure class first (transient infrastructure), then census every exposure
  point: the security-scan script
  ([run_agent_security_scans.sh](https://github.com/diazMelgarejo/orama-system/blob/main/scripts/ci/run_agent_security_scans.sh))
  had 6 pip install call sites and the two fixes together protected 2 (corrected 2026-11-16 from
  "8 sites, 3 protected" after a census of the script at `db536e15`; aguara and ramparts use go and
  cargo installs and are not pip sites).
- Durable shape: one shared env-tunable helper (PIP_INSTALL_ATTEMPTS, PIP_INSTALL_RETRY_DELAY_SEC)
  with linear per-attempt backoff, applied to every call site, keeping the explicit guarded failure
  and message at the site whose scan owns the accounting.
- Synthesis workflow that worked: classify hunks per integrative-merge, decide retire-or-absorb per
  PR, build on a trial branch from main in a dedicated worktree, smoke-test behavior with stubs before
  pushing, retire superseded PRs with superseded-by comments.

## PS 5.1 byte fidelity (verified on 5.1.26100.9818)

- ASCII scripts need no BOM; non-ASCII .ps1 needs a UTF-8 BOM and a real powershell.exe parse
  (without BOM the same script prints mojibake).
- Process bytes must never pass PowerShell redirection (re-encoded UTF-16LE, 10 true bytes became
  22) or Out-File -Encoding utf8 (BOM plus CRLF, 10 became 16). Raw byte capture must bypass
  PowerShell entirely.

Operational tools remain canonical: native lesson graduation, GossipBus emission, and the repo
verify gates. This card is evidence, not operator approval.

## Designated concrete exemplar (operator earmark, 2026-11-15)

The operator has earmarked **orama-system PR #516** (the CI pip-install retry synthesis: one shared
env-tunable `pip_install_retry()` helper applied to all 6 pip call sites, both sides strengths
amalgamated, #509/#511 retired with absorption credit, 31/31 CI checks green) as a solid concrete
example of what a real elegant synthesis looks like. The generalized method is canonicalized at
[fragment-synthesis.md](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/oramasys-method/references/fragment-synthesis.md)
(registered in the method SKILL.md references table), with PR #516 embedded as the worked example.
Reference cards updated in the same pass:
[docs/wiki/02](https://github.com/diazMelgarejo/orama-system/blob/main/docs/wiki/02-idempotent-installs.md)
(retry census),
[09](https://github.com/diazMelgarejo/orama-system/blob/main/docs/wiki/09-policy-fail-closed-and-checklist.md)
(fail-secure snapshot),
[17](https://github.com/diazMelgarejo/orama-system/blob/main/docs/wiki/17-line-endings-and-encoding.md)
(PS 5.1 byte fidelity) — branch `docs/metabolize-48h-lessons`.
