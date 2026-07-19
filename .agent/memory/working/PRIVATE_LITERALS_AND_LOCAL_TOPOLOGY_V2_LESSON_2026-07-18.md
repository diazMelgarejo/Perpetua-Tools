# Private Literals and Local Topology: v2 Carry-Forward Lesson

Date: 2026-07-18

## Executive Memory

Private identity literals and local topology are not documentation facts. They are local configuration facts.

The rule belongs in the repository. The sensitive values do not. A tracked repository may define:

- the invariant;
- the loader;
- the expected local-only file shape;
- synthetic tests;
- case-insensitive matching behavior;
- failure messages that use neutral labels.

It must not contain the actual private identity literal, a direct spelling of a private forbidden attribution literal, an encoded version of those literals, or real LAN device addresses.

## Final Verified State

Private literals:

- The tracked PT and Orama files were scrubbed of the private owner identity literal, the private forbidden-attribution literal, and the previously encoded private forbidden-attribution form.
- The actual private values live in a local-only file at the OpenClaw workspace root, outside both repositories.
- Both repos now ignore the local verboten file name in case a future agent copies it into a repo root.
- Repo code reads the local-only file through a generic loader and compares values case-insensitively.
- Tests use synthetic fixture values only.

Local topology:

- Tracked YAML must not contain real LAN IPs or device-specific DHCP state.
- PT `config/devices.yml` keeps Windows LAN fields empty and uses comments/env placeholders rather than real addresses.
- PT `config/models.yml` uses env-var defaults and loopback/local placeholders only.
- Runtime topology belongs in ignored local files and user state:
  - `.env.local`
  - `.env.lmstudio`
  - `~/.openclaw/state/last_discovery.json`
- These local topology files are ignored by both repos where applicable.

The verified pattern is:

```text
repo: policy + loader + synthetic fixtures
local parent folder: actual private literals
ignored env/state files: actual device topology
```

## The Important Realization

The first attempted fix was conceptually wrong: it tried to ban a literal while still spelling the literal in the ban rule, allowlists, tests, docs, and memory. That is the paradox. If the literal is genuinely private, then the tracked rule cannot quote it, even to say it is forbidden.

The correct design is a two-layer rule:

1. Tracked code and docs describe categories: configured private owner identity, configured forbidden attribution, configured local topology.
2. The actual category values are supplied by local-only files outside the repo or by ignored runtime state.

This is the same architectural instinct as token handling: a repository may validate that a token is absent, but it must not include the token as a fixture. Use synthetic values in tests.

## Case-Insensitive Means Actually Case-Insensitive

The rule must match private literals case-insensitively. Agents often run a case-sensitive grep, get a clean result, and stop too early. That misses title-case, lowercase, uppercase, and encoded remnants. The durable check is:

- scan with case-insensitive search;
- include `.git` metadata when checking local repositories;
- expire local reflogs if metadata contains scrubbed values;
- use the same casefold/lowercase semantics in repo hygiene code.

The scan itself must not print private literals in final reports. Report categories and counts, not values.

## Why This Matters for v2

v2 will have more agents, more repos, more generated docs, more PR bodies, more memory records, more branch surgery, and more local/runtime state. That increases the chance that an agent copies a private value from:

- a terminal transcript;
- a stale memory entry;
- a git reflog;
- a CI failure;
- a PR review comment;
- a test fixture;
- a local `.env` file;
- a historical document.

The answer is not less memory. The answer is better memory:

- keep recording lessons;
- keep committing useful `.agent/memory/**` entries when they are valuable;
- scrub values before writing;
- use neutral labels;
- put actual local values in local-only configuration.

Memory must preserve the shape of the lesson, not the sensitive payload.

## Three-Day Session Reflection

The past three days exposed a repeated pattern: the system was trying to coordinate at fleet scale while still carrying some single-agent habits.

What improved:

- We converged on explicit coordination surfaces instead of relying on one board.
- We treated Claude/Codex disagreements as evidence to reconcile, not as noise.
- We stopped trusting summaries when live repo state could be checked.
- We learned to separate authoritative policy from local/runtime values.
- We hardened PR #258 without abandoning PT memory.
- We kept the coordination-consolidation work scoped while still repairing adjacent infrastructure.

What hurt:

- Agents repeatedly confused "do not leak this value" with "stop recording memory."
- Agents sometimes preserved a forbidden literal by moving it from one tracked place to another.
- Tests embedded real values when synthetic fixtures would have proven the same behavior.
- Some old docs treated runtime LAN state as if it were durable configuration.
- Branch/PR repair work created enough context churn that memory had to become more explicit, not less.

The corrected doctrine:

- Do not amputate memory; sanitize it.
- Do not hardcode private values; externalize them.
- Do not remove coordination channels; converge them.
- Do not trust local git history blindly; scan it.
- Do not put live topology in shared config; make it runtime-local.
- Do not let a rule violate itself by quoting the secret it is trying to ban.

## Future Agent Checklist

Before committing memory, docs, tests, or git-guard changes:

- Search case-insensitively for private literal categories, not only exact expected spelling.
- Search for encoded forms if an earlier system used encoding to hide a value in tracked files.
- Check tracked files and local `.git` metadata when scrubbing an active checkout.
- Keep actual verboten values in the OpenClaw workspace-root local file, not in any repo.
- Keep real LAN/device addresses in ignored env/state files, not tracked YAML.
- Keep tests synthetic.
- Run repo hygiene after writing.
- If already-pushed history contains old values, treat history rewriting as a separate explicit operation.

## Short Rule

Tracked repos may know how to find private/local values. They must not contain the values.
