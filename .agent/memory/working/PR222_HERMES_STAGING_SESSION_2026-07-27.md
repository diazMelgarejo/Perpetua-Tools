# PR #222 Hermes staging session — lessons, reflection, takeaways (2026-07-27)

> **Cross-repo:** orama-system PR [#222](https://github.com/diazMelgarejo/orama-system/pull/222) (`cursor/hermes-staging-security-hardening-f559`)  
> **PT sibling:** [#291](https://github.com/diazMelgarejo/Perpetua-Tools/pull/291) (`cursor/skill-security-wording-memory-f559`)  
> **Head commits:** `da3c3251` (CodeRabbit 4792277312 + CIDF examples), `2bb88d95` (CIDF doctrine cherry-pick)

## Session arc

1. **PR body clobber** — Agent replaced full Hermes Phase B summary with aguara-only follow-up text.
2. **Restore** — Reconstructed original scope from `docs/v2/50-mesh-security-migration-ladder.md`, review gate plan, execution log; wrote append-only body (original Summary + chronological `## Follow-up:` blocks).
3. **CIDF doctrine** — Codified integrative editing on sideline branch `cursor/cidf-integrative-editing-f559` (local only, never pushed).
4. **CodeRabbit 4792277312** — Review fixes on PR branch: hermes-spawn, repo_hygiene fail-closed, MCP pin policy, glm52/openrouter opt-in profiles, portal TLS, migration trap.
5. **Consolidation** — User asked to move all uncommitted edits to PR #222; cherry-picked CIDF onto PR branch, pushed `da3c3251`, deleted orphan sideline with `git branch -D`.
6. **PR body follow-up** — Appended `## Follow-up: CodeRabbit review 4792277312 + CIDF examples` without touching original Summary.

## Gold nuggets (recall anchors)

| Topic | Rule |
|-------|------|
| PR descriptions | Append-only historical records — original purpose at top, dated `## Follow-up:` below (`lesson_3b13ab0a45d4`) |
| PR body recovery | `gh pr view` → session cache → canonical ladder/review-gate docs → integrative restore |
| Corpus amputation | Replacing full PR/memory/plan summary with latest delta only — anti-pattern row in CIDF `FRAMEWORK.md` |
| Sideline branches | Cherry-pick doctrine onto PR branch; `git branch -D` after verify (cherry-pick SHA ≠ original SHA) |
| Aguara on #222 | CI plumbing side quest — label in PR follow-up, not branch purpose |
| Skill wording | See `SKILL_SECURITY_WORDING_AGUARA_2026-07-27.md` + `lesson_0f75262a1392`, `lesson_18ab3b438ae6`, `lesson_61e28f748e08` |
| MCP install | `mktemp` + chmod 700; pin `pkg@<VERSION>`; no bare `@latest`; local `openclaw mcp serve` |
| hermes-spawn | Session ID allowlist; PID-file status; mode-700 runtime dir; lock on stop — no `AIAgent.chat` probe |
| repo_hygiene | Index-mode reads fail closed — no worktree fallback; decode errors → scan errors (LINT-013) |
| Portal pull | No bearer over plaintext HTTP — TLS / tunnel / scoped token |
| Merge order | #223 → operator backup → #224 + PT #287 → verify → **#222 last** |

## CodeRabbit 4792277312 — what landed (`da3c3251`)

### CIDF
- `bin/orama-system/cidf/SKILL.md` — Integrative Editing Doctrine + link to examples
- `bin/orama-system/cidf/references/integrative-editing-examples.md` — good/bad table (PR append-only, `@latest`, `/tmp` install race, hermes-spawn status, index fail-closed, no sudo, HTTP bearer, aguara wording)
- `FRAMEWORK.md` — corpus amputation anti-pattern (from earlier cherry-pick)

### Runtime / review fixes
- `skills/hermes-harness/hermes-spawn/SKILL.md` — bounded status, allowlist, private pid dir
- `scripts/review/repo_hygiene.py` + `tests/test_repo_hygiene.py` — fail-closed staged blob reads
- cursor/cline/MCP skill docs — pinned npx, mktemp installers
- glm52/openrouter — opt-in `*_PERSIST_SHELL_PROFILE=1`; no sudo on `~/.openclaw`
- Portal runbook — no bearer over HTTP
- migration operator — `trap` restores gateway on failure

## Agent reflection (this session)

**What went wrong:** Treating the latest CI delta (aguara remediation) as the PR's identity. That violated integrative-merge doctrine we were simultaneously codifying in CIDF — the remedy repeated the disease until the operator corrected it.

**What worked:**
- Append-only PR body structure survived multiple follow-up rounds (4786574258 → mesh harmonization → aguara side quest → 4792277312).
- Cherry-pick consolidated sideline doctrine onto the single PR branch without duplicate PRs.
- CodeRabbit outside-diff comments mapped cleanly to bounded, testable fixes (fail-closed index reads, PID status, pin policy).

**New takeaways:**
1. **Doctrine and execution must share a branch** when the PR is the delivery vehicle — sideline branches for "just docs" create merge debt and orphan SHAs.
2. **Recovery sources are ranked:** live `gh pr view` (if partial) → agent session cache → canonical plan docs → commit messages. Never invent scope from the latest commit message alone.
3. **Cloud agent limits are real** — no `rsync` (install-skills.sh fails), no `pytest` in VM; pre-commit `repo_hygiene` + CI are the honest validation story. Say so in test plan checkboxes.
4. **Side quests need explicit labeling** — aguara/Ramparts/Rust toolchain work on a Hermes staging PR belongs in a `## Follow-up … — side quest` block so merge reviewers preserve Phase B intent.
5. **Teaching corpus belongs in CIDF examples, not in PR bodies** — `integrative-editing-examples.md` quarantines bad patterns the same way `skillify/examples/bad/` quarantines attack-shaped commands.

## Environment notes (cloud VM)

```text
scripts/install-skills.sh  → fails (no rsync)
python3 -m pytest          → not available
pre-commit repo_hygiene    → passed on commit da3c3251
CI on push                 → agent-security + test suite (authoritative)
```

## Recall

```bash
python .agent/tools/recall.py "PR222 Hermes staging integrative editing"
python .agent/tools/recall.py "append-only PR description recovery"
python .agent/tools/recall.py "repo_hygiene fail closed index"
python .agent/tools/recall.py "hermes-spawn PID status"
```

## Related working memory

| File | Topic |
|------|-------|
| `SKILL_SECURITY_WORDING_AGUARA_2026-07-27.md` | Aguara + naive-agent literal execution |
| `MESH_SECURITY_MIGRATION_2026-07-26.md` | Mesh ladder merge order #223→#224→#222 |
| `HERMES_OPENCLAW_STAGING_2026-07-26.md` | Harness sync / profile install tracker |
| orama `cidf/references/integrative-editing-examples.md` | Canonical good/bad examples (PR #222) |

## Graduated lessons (this session)

| id | Topic |
|----|-------|
| `lesson_6fff093ccb00` | PR body clobber recovery (append-only restore) |
| `lesson_9a91e4244de6` | Sideline branch cherry-pick consolidation |
| `lesson_ca5230ce8eb2` | repo_hygiene index-mode fail-closed |
| `lesson_9581e059df66` | hermes-spawn PID-based status |
| `lesson_37fcf2a122d5` | MCP mktemp + npx pin policy |
| `lesson_9de94e84f50c` | Portal bearer requires TLS/tunnel |
| `lesson_7249ce91fd33` | GLM52/OpenRouter opt-in shell profiles |
| `lesson_b01f284b662e` | Cloud agent honest CI/test story |
| `lesson_0f4ba0603465` | Aguara remediation = labeled side quest |
| `lesson_83c53b4aabf1` | CIDF integrative editing + corpus amputation |
