# Perpetua Core PR #6 — Recovery, Review-State, and Architecture Lessons

Date recorded: 2026-09-13

Repositories involved:

- `oramasys/perpetua-core`
- `oramasys/agate`
- `diazMelgarejo/Perpetua-Tools` as the v1 canonical `.agent` memory store

Primary pull request:

- `https://github.com/oramasys/perpetua-core/pull/6`

This document records the errors, recovery sequence, review-state confusion, testing changes, and architectural decisions established while repairing `oramasys/perpetua-core` PR #6. It is intended as durable operational memory for future agents working across constrained or remote GitHub workspaces.

## 1. Incident: `src/tests/test_policy.py` corruption

The repository's `main` branch became CI-red after commit `ae52aff` (`test(policy): normalize dependency names in boundary check`). The commit message described a narrow dependency-name-normalization change, but the committed `src/tests/test_policy.py` blob was not a valid Python source file. The previous valid file had been replaced by binary/garbage content.

The last known-good pre-corruption source was commit `02ab8e1`. The correct recovery was therefore not to infer a replacement from the broken blob, but to:

1. recover the complete known-good Python test file from `02ab8e1`;
2. reconstruct the intended narrow dependency-name normalization semantically from the commit purpose and review context;
3. preserve all existing policy and compatibility tests;
4. verify the restored source as parseable Python before treating the incident as repaired.

This reinforces the broader integrity rule already learned from earlier corruption events: a commit message, tool success, or changed-file summary is not proof of valid remote bytes. Exact content and parser-level verification remain mandatory.

## 2. Reconstructed intended dependency guard

The dependency-boundary test needed to compare distribution identities rather than raw requirement strings. A naive split-based implementation could miss valid PEP 508 forms such as version specifiers, extras, or direct references.

The stricter reconstruction introduced a canonical requirement-name parser that:

- extracts the leading distribution token;
- treats `-`, `_`, and `.` as equivalent separators;
- normalizes those separators to `-`;
- lowercases the canonical name;
- remains effective when the requirement includes version constraints, extras, environment markers, or direct references.

The test suite explicitly covers equivalent forms such as:

- `oramasys-agate`
- `oramasys_agate>=0.1`
- `oramasys.agate[tests]~=0.1`
- `oramasys_agate @ git+https://...`

The architectural purpose is to prevent dependency-boundary bypass through syntactic variation.

## 3. TDD RED/GREEN sequence established in PR #6

A deliberate TDD sequence was used to prove the stronger packaging invariant.

### RED state

Commit:

- `6411f5338611e813d79d67a1e88419ce9f1d46f3`

The new invariant `test_core_does_not_publish_agate_as_an_optional_dependency()` was added while `test-agate-compat` still existed in `[project.optional-dependencies]`.

CI failed intentionally. That failure was evidence that the invariant detected exactly the packaging regression we wanted to forbid.

### GREEN state

Commit:

- `8948888007eee84dc92ace430c0dda1ce75f3705`

The temporary `test-agate-compat` optional extra was removed entirely from `pyproject.toml`.

The Agate compatibility fixture was moved to:

- `requirements/test-agate-compat.txt`

with an immutable Agate pin:

- `oramasys-agate @ git+https://github.com/oramasys/agate.git@41a0da9d52e0131049a1469234ac56f6990fc635`

CI then installed the repository and compatibility fixture in two explicitly separate steps:

1. `python -m pip install -e '.[dev]'`
2. `python -m pip install -r requirements/test-agate-compat.txt`

At that head, the Python 3.11 and Python 3.12 matrix passed, including fixture installation, pytest/coverage, and compile smoke.

## 4. Architectural decision: Agate must not be a Core package dependency

The final invariant is stronger than merely removing Agate from required runtime dependencies.

Core must not publish Agate through:

- `project.dependencies`;
- any `[project.optional-dependencies]` extra;
- any other package metadata that makes Agate appear to be a dependency owned by Core.

Compatibility testing is allowed, but Agate is installed by the test environment independently as an external fixture.

This prevents test convenience from reintroducing architectural ownership through packaging metadata.

Canonical direction:

**Agate decides policy → Oramasys composes → Core executes.**

Consequences:

- Agate owns hardware-policy interpretation and verdicts.
- Oramasys composes higher-level routing decisions.
- Core executes approved decisions and must not reacquire policy ownership.
- The deprecated Core compatibility façade may delegate to Agate, but it must not duplicate Agate policy logic.
- Importing Core must not eagerly import Agate.
- Legacy callers may remain behaviorally compatible while migration proceeds.
- An external test fixture is not equivalent to a published package dependency.

## 5. Added packaging invariants

Two distinct tests are required because they enforce different failure modes.

### Runtime dependency invariant

`test_core_does_not_declare_agate_as_a_runtime_dependency()` ensures Core never declares Agate as a required package dependency.

### Optional dependency invariant

`test_core_does_not_publish_agate_as_an_optional_dependency()` ensures a future change cannot remove Agate from required dependencies only to reintroduce it quietly through an optional extra.

This second invariant was necessary because optional dependencies are still published Core metadata and therefore still imply a dependency relationship owned and advertised by Core.

## 6. CodeRabbit review-state confusion

CodeRabbit review `5188519896` initially reported:

> The dependency declaration contradicts the new packaging invariant and leaves CI failing. Move the compatibility dependency to a non-published dependency group before merge.

The finding was technically correct for the deliberate RED commit `6411f533...`, because that commit intentionally left `test-agate-compat` in `project.optional-dependencies` so the new invariant would fail.

The apparent disagreement arose because CodeRabbit's formal review metadata showed that it had reviewed only through `6411f533...`, even though a later GREEN head already existed.

The correct response was not to follow the stale recommendation literally. The correct response was to verify the exact review coverage and compare it against the current PR head.

After the current head `8948888...` was presented explicitly, CodeRabbit re-evaluated the repository state and confirmed:

- `pyproject.toml` no longer published Agate as a runtime or optional dependency;
- CI installed Core with `.[dev]`;
- CI installed Agate separately from `requirements/test-agate-compat.txt`;
- the dependency-boundary invariant was satisfied;
- the requirements-file arrangement was stricter than the proposed dependency-group arrangement because Agate did not appear in Core's project dependency declarations at all.

CodeRabbit then resolved the review thread and recorded the architectural learning.

### Durable lesson

A review comment is scoped to the commit range the reviewer actually examined. Review submission time alone does not establish that the reviewer analyzed the latest head.

When an automated reviewer appears to disagree with a later fix:

1. inspect its reviewed commit range;
2. inspect the current PR head SHA;
3. compare the exact current diff;
4. check current CI on the exact head;
5. distinguish a stale finding from a current one;
6. reply with exact-head evidence rather than blindly implementing a historical recommendation.

This is another form of the wider authority rule: cached or historical review state is not current authority.

## 7. Docstring-coverage hardening

CodeRabbit also reported touched-function docstring coverage below the desired threshold.

The response was deliberately not cosmetic. A documentation-grade pass was applied in commit:

- `a7a6624092a747538094f3d07779a0fa09fb8da9`

Every touched test/helper function in `src/tests/test_policy.py` was given a formal explanatory docstring, making the touched-function set structurally 100% documented rather than merely targeting the minimum 80% threshold.

The docstrings were used to preserve architectural intent, including:

- Agate owns policy interpretation and verdicts;
- Oramasys composes;
- Core executes;
- Core must not reacquire policy ownership;
- legacy compatibility must normalize onto Agate's canonical `PolicyStore`/`ModelSpec` model rather than create a Core-owned shadow structure;
- lazy import behavior prevents the compatibility façade from becoming a hard import-time dependency;
- policy verdicts such as `NEVER`, `PREFER`, and `ALLOW` pass through without reinterpretation;
- explicit model hints cannot override an all-`NEVER` policy;
- requirement spelling variation cannot evade package-boundary checks;
- optional extras remain prohibited for Agate;
- external CI fixture installation is the approved compatibility-test arrangement.

The docstring-only head again passed the Python 3.11 and Python 3.12 CI matrix, including Core installation, external Agate fixture installation, pytest/coverage, and compile smoke.

## 8. Review and recovery process lessons

The incident reinforces several process requirements for future agents.

### Do not infer intended bytes from a corrupt commit

Use the last known-good file plus independently supported intended semantic changes. Preserve a clear distinction between:

- restored historical source;
- reconstructed intended delta;
- current verified remote content.

### Preserve TDD evidence

If a test is introduced specifically to prove an invariant, a deliberate RED commit can be valuable evidence. Do not later misinterpret that commit as the intended final state.

### Separate package ownership from test-environment composition

A dependency required only to exercise compatibility in CI should not automatically be placed into a package's published metadata. The package boundary and the CI environment are distinct authority surfaces.

### Review findings are temporal evidence

Automated review findings must be evaluated against the exact commit they reviewed. A finding valid at an earlier head can become obsolete after a later correction.

### Prefer stronger invariants when they are architecturally cleaner

The final requirements-file arrangement was intentionally stricter than placing Agate into a non-published dependency group inside `pyproject.toml`: it keeps Agate out of Core's project dependency declarations altogether.

## 9. Canonical architecture after PR #6

The hierarchy established by the recovery remains:

1. **Agate** — hardware authority and policy interpretation.
2. **Oramasys** — composition and higher-level routing.
3. **Perpetua Core** — execution kernel for approved decisions.

Core may retain a transitional/deprecated compatibility wrapper, but that wrapper must remain:

- lazy;
- delegating;
- non-authoritative;
- non-duplicative;
- free of published Agate dependency ownership.

## 10. Evidence references

Perpetua Core PR:

- `https://github.com/oramasys/perpetua-core/pull/6`

Important commits:

- last known-good pre-corruption test file: `02ab8e1`
- corrupt commit: `ae52aff`
- TDD RED dependency-boundary commit: `6411f5338611e813d79d67a1e88419ce9f1d46f3`
- GREEN external-fixture architecture commit: `8948888007eee84dc92ace430c0dda1ce75f3705`
- documentation/docstring hardening commit: `a7a6624092a747538094f3d07779a0fa09fb8da9`

Agate fixture pin:

- `41a0da9d52e0131049a1469234ac56f6990fc635`

CodeRabbit review:

- `https://github.com/oramasys/perpetua-core/pull/6#pullrequestreview-5188519896`

## 11. Memory status

This is a working-memory dossier, not a replacement for accepted semantic lessons. Future graduation into semantic lessons should remain additive and preserve the evidence chain above.
