# Contributing to Perpetua-Tools

Perpetua-Tools is the top-level idempotent multi-agent orchestrator for Mac +
Windows. Useful contributions include orchestrator and agent-lifecycle code,
memory-tooling and skills under `.agent/`, CI and repo-hygiene improvements,
tests, and documentation. Changes that belong in a sibling repo
([orama-system](https://github.com/diazMelgarejo/orama-system) for reasoning
methodology, ECC Tools for subagent selection, autoresearch for research
workflows) should be proposed there, not vendored in by reflex.

Both humans and coding agents contribute here. The same standards apply to
both: scoped work, attributable commits, visible verification, and an honest
description of residual risk.

## Before you start

- Search existing issues, PRs, and `.agent/memory/` lessons before proposing
  new work — the decision or implementation may already exist.
- Discuss design-level or cross-cutting work before implementing it.
- Read [`SECURITY.md`](SECURITY.md) and
  [`.github/AUTHORIZED_CONTRIBUTORS.md`](.github/AUTHORIZED_CONTRIBUTORS.md).
- Commit identity must match `AUTHORIZED_CONTRIBUTORS.md`: the owner authors as
  `diazMelgarejo@gmail.com` or `Lawrence@cyre.me`; AI-assisted commits list the
  assistant as `Co-authored-by`, never as the git author. Note that git author
  identity does **not** by itself distinguish a human from an autonomous agent
  in this stack — agents inherit the local git config.

## Reporting issues

Include the observed behavior, expected behavior, relevant version or
environment (Mac/Windows, Python version), and minimal reproduction steps.
Do **not** open public issues for vulnerabilities — follow
[`SECURITY.md`](SECURITY.md) and report privately.

## Submitting a pull request

1. Branch from the current default branch (`main`). Do not develop directly on
   `main` — a pre-push guard blocks direct pushes (escape hatch
   `ALLOW_MAIN_PUSH=1` exists for explicitly authorized, reviewed exceptions).
2. Keep the PR to **one logical change**. Split unrelated fixes into separate
   PRs so each can be assessed on its own merit.
3. Add or update tests and documentation wherever behavior changes.
4. Run repo hygiene and the relevant tests locally before requesting review:
   `python3 scripts/review/repo_hygiene.py .` and `python3 -m pytest`.
5. Open a **draft** PR until its description, evidence, and risk notes are
   complete. Request review only when the body is done and checks pass.
6. Complete the PR template.

### Keep memory writes tool-native

Changes to `.agent/memory/` should go through the memory tooling
(`.agent/tools/learn.py`, `graduate.py`, and friends), not hand-edited JSONL,
so referential integrity (a lesson's `evidence_ids` resolving to a real
episodic record) is preserved. If you must reconstruct a record by hand,
verify the invariant programmatically and say so in the PR.

## Review and follow-up

Push follow-up commits to the same branch and re-request review after material
changes. When addressing review findings, prefer the **post-review
micro-remediation** discipline: cluster findings by root cause and fix the
abstraction once rather than patching each comment in isolation; before any
destructive git operation (reset, history rewrite), create a safety ref first;
and verify every finding is fixed, superseded by a deeper fix, or documented as
not-applicable — never silently dropped.

## Conduct and support

Be respectful and constructive. Use GitHub issues or discussions for help. This
project is pre-release and moving toward a 2.0 repo; expect fast iteration and
prefer additive, well-evidenced changes over sweeping rewrites.
