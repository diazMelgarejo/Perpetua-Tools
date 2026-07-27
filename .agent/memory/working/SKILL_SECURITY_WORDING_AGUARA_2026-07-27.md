# Skill security wording — aguara CI & naive-agent literal execution (2026-07-27)

> **Cross-repo:** orama-system PR [#222](https://github.com/diazMelgarejo/orama-system/pull/222)  
> **Canonical card:** `orama-system/bin/orama-system/skills/skillify/references/skill-security-wording-reference-card.md`

## Problem

`agent-security` CI runs **aguara** on `bin/orama-system/skills` with
`--ci` (fail on HIGH) plus a baseline. Several rules are
**non-baselineable** — they always report and can gate even when legacy
findings are baselined.

Fixing one gating finding often exposed the next (whack-a-mole) until wording
was changed across skill docs — not scanner configuration.

## Unintentional hack (why wording matters)

Skill markdown is loaded by other agents. **Strongly worded imperative commands**
(`claude mcp add …`, `curl | bash`, `source ~/.env…` next to HTTP POST,
`>> ~/.zshrc`) are not only scanner hits:

- A **naive or smaller model** may treat them as mandatory runbook steps and
  execute without the review the author assumed.
- That is an **unintentional prompt-injection / supply-chain** path: the skill
  becomes remote-control text for whatever reads it.

We word skills so humans keep **review-before-run**, and aguara can **baseline
legacy noise** while **new** attack-shaped text still fails CI.

## Teaching paradox (resolved)

You **can** teach the negative rule. You **cannot** embed literal bad commands
in production `SKILL.md` without the same scanner + naive-agent risks.

| Layer | Where | What |
|-------|-------|------|
| Doctrine | `skill-security-wording-reference-card.md` | Safe patterns, rule index |
| Curriculum | `skillify/examples/bad/security-wording-anti-patterns.md` | Literal bad→good; `<!-- aguara-ignore-next-line -->` per bad line |
| Production | `SKILL.md` | Good patterns only; 0 gating in CI |

Euphemizing bad patterns failed pedagogy. Quarantined curriculum with inline
ignore is the intended pattern (labeled vaccine samples, not scanner weakening).

## Koan

> To teach what must not be run, do not write it where it will be run.  
> The forbidden command belongs in the quarantined curriculum
> (`skillify/examples/bad/`, `aguara-ignore-next-line` per bad line),  
> not on the operator cheat sheet (`SKILL.md`).  
> Euphemism teaches nothing; literal bad examples behind explicit scanner
> ignore teach everything — without weakening CI or handing naive agents a
> remote-control script.

Graduated: `lesson_*` via `learn.py` — recall: `python .agent/tools/recall.py "skill security koan"`

## Rules hit in PR #222 remediation (examples)

| Rule | Issue | Safer wording |
|------|-------|----------------|
| EXTDL_006 | `cline mcp install … -- npx` | Prose: register in MCP UI with launch command |
| CRED_021 | `.env` + POST in same block; `process.env` + fetch POST | Env var names only; `process['env']` in JS examples |
| EXTDL_005 | “Add/append to ~/.zshrc” | “Wires into existing login profiles when present” |
| SUPPLY_005 | `# CI` in docstring + subprocess in file | “skip auth-required canaries” (no CI token) |
| SUPPLY_003 / EXTDL_013 | `curl \| bash` | Vetted repo script + pin + review |
| SSRF_002 | LAN IPs in tracked md | Env vars / redacted placeholders |

## Validation (orama repo)

```bash
aguara scan bin/orama-system/skills \
  --ci \
  --baseline config/agent-security/aguara-skills.baseline.json \
  --disable-rule TOXIC_CROSS_002

aguara explain <RULE_ID>
```

Regenerate baseline only after reviewed intentional changes:

```bash
aguara scan bin/orama-system/skills \
  --write-baseline config/agent-security/aguara-skills.baseline.json \
  --disable-rule TOXIC_CROSS_002
```

## PT memory pipeline entry

Graduated via `learn.py` — search: `skill security wording aguara naive agent literal`

## Recall

```bash
python .agent/tools/recall.py "aguara skill wording naive agent literal"
python .agent/tools/recall.py "EXTDL_006 CRED_021 skill security"
```

## Related

| Doc | Topic |
|-----|-------|
| `MESH_SECURITY_MIGRATION_2026-07-26.md` | Mesh / gossip / LAN security ladder |
| `PRIVATE_LITERALS_AND_LOCAL_TOPOLOGY_V2_LESSON_2026-07-18.md` | IP literal scrub |
| orama `skill-architecture-guide.md` § LINT-016 | Repo lint pointer |
