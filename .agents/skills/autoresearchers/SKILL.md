---
name: autoresearchers
description: "Coordinate AutoResearcher fan-out, evidence collection, branch ownership, and handoff into an integration PR."
---

# AutoResearchers

Use `scripts/launch_researchers.py` and the repository's autoresearch orchestration surfaces for parallel evidence collection. Apply the Oramasys method before spawning or assigning researchers.

## Required shared discipline

Load:

- [Branch-Local Review Remediation](../../../.agent/references/branch-local-review-remediation.md)
- [`../agent-methodology/SKILL.md`](../agent-methodology/SKILL.md)
- [`../code-review/SKILL.md`](../code-review/SKILL.md)
- [`../git-history-surgery/SKILL.md`](../git-history-surgery/SKILL.md)

## Researcher contract

Each researcher must record:

- task claim and owning branch;
- files or evidence surfaces inspected;
- assumptions and confidence;
- whether it made writes or remained read-only;
- exact commit or handoff artifact;
- unresolved risks.

Researchers may inspect any branch, but they do not move review fixes across branch boundaries. A researcher working from evidence produced by a PR submits its remediation to that PR's owning branch or returns a read-only recommendation to the integrator.

## Integration

One integrator synthesizes researcher outputs, resolves overlaps by invariant, and verifies the final branch. Do not let independent researchers write competing fixes to `main` or to the same file without an explicit ownership handoff.
