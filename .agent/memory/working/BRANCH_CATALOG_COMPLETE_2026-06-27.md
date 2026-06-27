# Branch catalog — complete tree-twin inventory

Generated: **2026-06-27 10:07 UTC**

> Method: `reanchor_scan.sh <repo> origin/main heads` + `git cherry -v` per NEEDS-REANCHOR.
> **True unique** = cherry lines with `+`. Graft count is first-parent walk estimate only.

## Summary

| Repo | main | Merged | Re-anchor only | PR candidates (`+`>0) |
|------|------|--------|----------------|---------------------|
| Perpetua-Tools | `9db5cf4` | 12 | 4 | 10 |
| orama-system | `3a5ea2a` | 6 | 2 | 9 |

## Perpetua-Tools

`origin/main` @ `9db5cf4` | **26** local branches | `reanchor_scan` + `git cherry -v`

| Class | Count |
|-------|-------|
| MERGED/in-main | 12 |
| Re-anchor only (cherry `+` = 0) | 4 |
| True unique work (`+` > 0) | 10 |

### MERGED/in-main

| Branch | Tip | Twin | Subject |
|--------|-----|------|---------|
| `2026-05-27-009-fix4-5-path-boundary-mcp` | `bf3908e` | `920a64a37` | feat(mcp): wire path-boundary enforcement into AlphaCla |
| `2026-05-28-004-dependabot-security-bumps` | `bc6d850` | `2ff0e8693` | refactor(net_utils): print→log, netifaces dep, timeout/ |
| `2026-06-06-001-model-bump-opus-4-8-and-prompt-caching` | `32f770c` | `32f770c79` | fix(model): correct malformed model IDs to real strings |
| `cursor/critical-bug-investigation-0df5` | `ad702c5` | `ad702c525` | refactor(rag): cache gossip bus, document env mutation, |
| `cursor/critical-bug-investigation-a924-followup` | `91fcdcd` | `91fcdcdec` | fix(PR-135): close CodeRabbit threads at memory write b |
| `feat/ip-aware-discovery` | `8fc5b55` | `6f422c7ae` | fix(discovery): enforce LM Studio Mac mirror exclusion  |
| `feat/perpetua-submodule-upgrade` | `39872a5` | `f1d2c39a4` | chore(.agent/memory): graduate 3 new lessons from 2026- |
| `fix/pt71-clean` | `3b5e6bf` | `305eab830` | fix(review): address remaining PT #71 CodeRabbit commen |
| `lesson-pt126-local` | `ce496ea` | `ce496ea5d` | learn: pre-push hook fails closed when worktree dir is  |
| `rebase-pt126-local` | `6c006bc` | `6c006bc77` | merge(main): resolve .agent/memory + vendor/ecc-tools c |
| `rebase-pt127-local` | `5556a7a` | `668bf9146` | merge(main): resolve conflicts — import paths, GPU_BOX  |
| `wip/preserve-20260614` | `07f27ce` | `07f27ce78` | docs(submodule): record vendor/ecc-tools local-only add |

### True unique work (`+` commits)

| Branch | Tip | Graft est. | `+` | Twin | Subject |
|--------|-----|------------|-----|------|---------|
| `fix/pt71-review-v2` | `1d72630` | 9 | **9** | `aa912835e` | fix(install): restore install.sh executable b |
| `fix/ci-71` | `8202ac3` | 8 | **7** | `0bcc99e1f` | fix(alphaclaw_manager): handle progress-log p |
| `fix/pt71-onto-main` | `98b6784` | 7 | **7** | `aa912835e` | fix(review): address CodeRabbit comments on P |
| `fix/ci-69` | `cf094bd` | 6 | **6** | `0bcc99e1f` | fix(install): fail-fast Ollama probe with sin |
| `2026-06-11-001-win-endpoint-discovery-sync` | `7985468` | 5 | **5** | `bea476a4c` | fix(gateway): idempotency precedence — comman |
| `2026-06-26--dev-recalib-cursor-agent` | `bdcfb53` | 2 | **2** | `9db5cf429` | docs(agent): platform line-ending turf rule — |
| `temp-recovery` | `7492c66` | 2 | **2** | `8f8cfce46` | chore: document symlink portability policy |
| `chore/domain-knowledge-windows-shims` | `9435b9e` | 1 | **1** | `9db5cf429` | docs(agent): steer Windows git/bash/gbrain sh |
| `clean-pt127` | `1ab3ed2` | 1 | **1** | `668bf9146` | fix(routing): live Win endpoint tracking + Ma |
| `recover/2026-05-31-codex-plan-revision` | `cdf7bdf` | 2 | **1** | `5f1d57520` | docs(plan): fold in Codex review — version ta |

#### `2026-06-11-001-win-endpoint-discovery-sync`

```text
+ fdccd5b75ebb91776f11db52ceb21416950e2b7b auto-save: pre-compaction checkpoint
+ 6ebe3babcca51c80fabd80b93779a21919b8c65b fix(routing): Win endpoint tracks live discovery + syncs all holders
+ 2fc8c24143a7b0beebc10a80c05696f4f9a7ba82 feat(routing): derive model `online` from a live probe, not static config
+ d464528ab36e1dc12ab455d853f09cdc3a758bdb fix(routing): Mac orchestrator = ollama-localhost first, affinity-safe, self-healing
+ 79854680ef8469acfa47bccde38e99a0f5a8c177 fix(gateway): idempotency precedence — commandeer, then start, then install
```

#### `2026-06-26--dev-recalib-cursor-agent`

```text
+ f78d5c251dfe5a90a16bee4e05fc4ca30367b30c chore(agent): 2026-06-26 dev-recalib — branch triage, Windows shims, review queue
+ bdcfb53d0e2683c63dabfd204a5bab1e51804694 docs(agent): platform line-ending turf rule — CRLF on Windows, LF elsewhere
```

#### `chore/domain-knowledge-windows-shims`

```text
+ 9435b9edf5e6384c49b4b21b91af3df3857f3824 docs(agent): steer Windows git/bash/gbrain shims into DOMAIN_KNOWLEDGE
```

#### `clean-pt127`

```text
+ 1ab3ed2119484f3259bd48ad58ca54378203fb90 fix(routing): live Win endpoint tracking + Mac affinity + gateway idempotency
```

#### `fix/ci-69`

```text
+ 69de745c199d0ad151c675e1d57dc518ba37f0a3 feat(mcpb): submodule Claude-Desktop-LLM and real MCPB install
+ 1f22a9a44a0fefc5cc3e520457872e9a3669e541 📝 Add docstrings to `cursor/claude-desktop-mcpb-submodule-74e2`
+ 74e53a4f2d44050213528087a5bcfcdc7818c3dd fix: apply CodeRabbit auto-fixes
+ 8ad6e631c188356ad619a9baf0092e26bb0dee7d 📝 CodeRabbit Chat: Add unit tests for PR changes
+ c62089445a2e92e6018f3ff96117a4189de0408d 📝 Add docstrings to `cursor/claude-desktop-mcpb-submodule-74e2`
+ cf094bdab0ef6d3a52b2a862c1e6a6528f90882e fix(install): fail-fast Ollama probe with single curl --max-time 5
```

#### `fix/ci-71`

```text
+ 69de745c199d0ad151c675e1d57dc518ba37f0a3 feat(mcpb): submodule Claude-Desktop-LLM and real MCPB install
+ 189468f4176336d2055edd2f2e8b41d0c4124c0f fix(alphaclaw-adapter): startServer pidFile opts ReferenceError
+ 1f7da496f3010bdd8fc2991773d8b94ddeb0e97b test(alphaclaw_manager): regression tests for bootstrap JSON parsing
+ 92dfe548b6bb5b7e72f39e63c407b3fa73f14ddd 📝 CodeRabbit Chat: Add generated unit tests
+ 5ce0c15c5dc80e84c2d76fde349ce77edd32eec6 📝 CodeRabbit Chat: Add unit tests
+ 38a493b734eb5b07e8ddb5e389594a8d5d84d3d8 📝 CodeRabbit Chat: Add unit tests
+ 8202ac37f0401c98e2813e775955257ed5911a87 fix(alphaclaw_manager): handle progress-log prefix in _parse_bootstrap_json
```

#### `fix/pt71-onto-main`

```text
+ 061c0eee1ed6d7d3880436171ae7941768ff5da6 fix(alphaclaw-adapter): startServer pidFile opts ReferenceError
+ e9c4ab83343873ef0c8192ae14a968c9a55e3b78 test(alphaclaw_manager): regression tests for bootstrap JSON parsing
+ 33bb9e90f43a8218065acd15c8d3616259722e96 📝 CodeRabbit Chat: Add generated unit tests
+ c8ba706a89e656c10668905fd0e4e08e50a61f31 📝 CodeRabbit Chat: Add unit tests
+ f4ab81057b82491256122b76c4af58d8b48e8e9d 📝 CodeRabbit Chat: Add unit tests
+ 07cd00e479fa092ad18e4f9638b40539806e85df fix(alphaclaw_manager): handle progress-log prefix in _parse_bootstrap_json
+ 98b6784a4adea6227b45cc096aacfa62553ea1d1 fix(review): address CodeRabbit comments on PT #71
```

#### `fix/pt71-review-v2`

```text
+ 061c0eee1ed6d7d3880436171ae7941768ff5da6 fix(alphaclaw-adapter): startServer pidFile opts ReferenceError
+ e9c4ab83343873ef0c8192ae14a968c9a55e3b78 test(alphaclaw_manager): regression tests for bootstrap JSON parsing
+ 33bb9e90f43a8218065acd15c8d3616259722e96 📝 CodeRabbit Chat: Add generated unit tests
+ c8ba706a89e656c10668905fd0e4e08e50a61f31 📝 CodeRabbit Chat: Add unit tests
+ f4ab81057b82491256122b76c4af58d8b48e8e9d 📝 CodeRabbit Chat: Add unit tests
+ 07cd00e479fa092ad18e4f9638b40539806e85df fix(alphaclaw_manager): handle progress-log prefix in _parse_bootstrap_json
+ f48eab0244b9850ebefcbd8cacf843f03179766f fix: apply CodeRabbit auto-fixes
+ b2b7638ae0cadbd430381340febdafe16fb36508 fix(review): resolve remaining PT #71 CodeRabbit comments
+ 1d72630205a4fa5da2f2783c8b88d727ad7c1744 fix(install): restore install.sh executable bit (mode 100755)
```

#### `recover/2026-05-31-codex-plan-revision`

```text
+ 79a3ddaacd007ffbaa898742a5486d8edc67534b test(user-input-queue): isolate queue state from prior-test bleed
```

#### `temp-recovery`

```text
+ 18ebde8a47ffd295ada03793b71f758be3340fb9 feat: implement 3-tier priority IP detection
+ 7492c660d506782f1802a5aa3cd704dc8f02ac90 chore: document symlink portability policy
```

### Re-anchor only (`+` = 0)

| Branch | Tip | Graft est. | Twin |
|--------|-----|------------|------|
| `2026-04-25-perpetua-recovery` | `15345fc` | 1 | `e68ee70e8` |
| `2026-06-01-073-fix-test-portability` | `753ef1b` | 1 | `2d6b82110` |
| `tmp-pr42-test` | `b77aaae` | 1 | `5f9d67c84` |
| `wt-pr42` | `b77aaae` | 1 | `5f9d67c84` |

---

## orama-system

`origin/main` @ `3a5ea2a` | **17** local branches | `reanchor_scan` + `git cherry -v`

| Class | Count |
|-------|-------|
| MERGED/in-main | 6 |
| Re-anchor only (cherry `+` = 0) | 2 |
| True unique work (`+` > 0) | 9 |

### MERGED/in-main

| Branch | Tip | Twin | Subject |
|--------|-----|------|---------|
| `feat/hermes-harness-onboarding` | `c75d352` | `c75d35298` | fix(canaries+discover): gate LM_READY marker; normalize |
| `feat/openclaw-codex-app-server` | `70ce2a6` | `350b29072` | docs(oramaclaw): vendor sync mechanism — untracked PT m |
| `feat/pt-orama-next` | `d73d503` | `5b86bb679` | docs(wiki): merge 2026-06-22 lessons into git-hygiene d |
| `fix/f6-f8-security-hardening` | `d37a182` | `b251f9099` | fix(security): harden openclaw-add-secret (F6) and cc-o |
| `merge/pr-99-self-reflection` | `8101984` | `8231084ea` | merge: resolve PR #99 conflicts — hermes-harness harmon |
| `test/pt-threat-id-reanchor` | `8a62421` | `73cacc3e3` | feat(skillify): narrow thin-wrapper install to Codex .a |

### True unique work (`+` commits)

| Branch | Tip | Graft est. | `+` | Twin | Subject |
|--------|-----|------------|-----|------|---------|
| `2026-06-13-001-post-fable5-ac-regression-repair` | `90176ed` | 192 | **11** | `a156104f6` | fix(goal): repair 3 AC regressions introduced |
| `v1.1-oramasys-Fable-5-preparation-part-1` | `9851b1f` | 191 | **10** | `a156104f6` | fix: correct fallback chain order — LM Studio |
| `2026-06-14-001-omniroute-ops-and-local-fallback` | `d0f950b` | 216 | **7** | `a156104f6` | fix(omniroute): add settings.json env-block r |
| `2026-06-14-002-omniroute-settings-env-fix` | `d0f950b` | 216 | **7** | `a156104f6` | fix(omniroute): add settings.json env-block r |
| `2026-06-13-001-ac-regression-repair-v2` | `2288b90` | 188 | **6** | `a156104f6` | fix(tests): fix residual env-isolation flake  |
| `wip/preserve-local-main-20260614` | `cdf120e` | 187 | **6** | `a156104f6` | feat(distill-fable-5): v1 CLI complete, Group |
| `2026-06-26--dev-recalib-cursor-agent` | `f553864` | 2 | **2** | `3a5ea2a89` | fix(windows): normalize gstack-brain-sync.cmd |
| `fix/pr135-lint006-windows` | `148c86f` | 1 | **1** | `b251f9099` | fix(hygiene): LINT-006 Windows user-profile p |
| `wip/vitest-scratch` | `85f5905` | 1 | **1** | `3a5ea2a89` | wip: vitest scratch + tdd-gate docs (restored |

#### `2026-06-13-001-ac-regression-repair-v2`

```text
+ b8c39ddc17dd34bc694b4755fce4a278ed70cd40 feat(start): ollama idempotent startup, per-profile config, MCP exposure, graceful shutdown
+ 591b9d1a8cdcbe37b2baa6e4275cca756d3d52af chore(config): openclaw auto-sorted mac-orchestrator.json (lmstudio-mac models)
+ 48bfa6d934e8c612bebc2a400f35141dc31069c4 arch: ollama first-class priority on Mac (qwen3.5:9b-nvfp4 + LM Studio Win)
+ c3d7463f6826ed2bf7317a0418de165b2fc35639 fix(security): redact committed secrets and harden scanning gates
+ 254130d9b2afd44477128da69c6a0e6185b94d01 fix(goal): repair 3 AC regressions introduced after PR #81/#82
+ 2288b9050cb3e12719b44e73a189cf7fe93fd722 fix(tests): fix residual env-isolation flake in test_perpetua_tools_root_used_when_path_env_not_set
```

#### `2026-06-13-001-post-fable5-ac-regression-repair`

```text
+ b8c39ddc17dd34bc694b4755fce4a278ed70cd40 feat(start): ollama idempotent startup, per-profile config, MCP exposure, graceful shutdown
+ 591b9d1a8cdcbe37b2baa6e4275cca756d3d52af chore(config): openclaw auto-sorted mac-orchestrator.json (lmstudio-mac models)
+ 48bfa6d934e8c612bebc2a400f35141dc31069c4 arch: ollama first-class priority on Mac (qwen3.5:9b-nvfp4 + LM Studio Win)
+ c3d7463f6826ed2bf7317a0418de165b2fc35639 fix(security): redact committed secrets and harden scanning gates
+ 329d20c1b946e24c55d41e713c91586e90b3b465 docs(distill-fable-5): preserve original pre-autoplan versions in archive (baseline for v1/v2 comparison)
+ cdf120e11c54b981c2767fe518e8cf3b572ab2dc feat(distill-fable-5): v1 CLI complete, Group A kickoff unblocked
+ 0a1972614ea1ae3930fa22f4a0b64402ffc4e67d fix: upgrade esbuild to 0.28.1 (GHSA-gv7w-rqvm-qjhr)
+ c9a9aa4bc41ebdfff19f7f9d9248b682f7741c69 fix: verify_before_done.py --check plan skips task-plan in non-interactive mode
+ 887aa5561e9f0485cfb8867c02c33f321fc99b1a fix: address coderabbit review — non-interactive flag, dir resolution, plan check
+ 9851b1f7a9a30b379b44006ae5fdce66ff0194fd fix: correct fallback chain order — LM Studio Mac is last, not third
+ 90176ed747d90676de72c3dc95c9c8541d69d046 fix(goal): repair 3 AC regressions introduced after PR #81/#82
```

#### `2026-06-14-001-omniroute-ops-and-local-fallback`

```text
+ b8c39ddc17dd34bc694b4755fce4a278ed70cd40 feat(start): ollama idempotent startup, per-profile config, MCP exposure, graceful shutdown
+ 591b9d1a8cdcbe37b2baa6e4275cca756d3d52af chore(config): openclaw auto-sorted mac-orchestrator.json (lmstudio-mac models)
+ 48bfa6d934e8c612bebc2a400f35141dc31069c4 arch: ollama first-class priority on Mac (qwen3.5:9b-nvfp4 + LM Studio Win)
+ c3d7463f6826ed2bf7317a0418de165b2fc35639 fix(security): redact committed secrets and harden scanning gates
+ b23483bcf136de77b9b4e150497d19257fb503da feat(omniroute): add full disable/re-enable runbook + local API fallback
+ bd173c815ef2732b586546eb75f784a447a03020 chore(omniroute): mark sidecar DISABLED in SKILL.md (2026-06-14)
+ 8548dbe8c2092709dc7f9eb9bcdb57bcab5b7103 fix(test): move local-api-fallback body to references/ to stay under 500-line gate
```

#### `2026-06-14-002-omniroute-settings-env-fix`

```text
+ b8c39ddc17dd34bc694b4755fce4a278ed70cd40 feat(start): ollama idempotent startup, per-profile config, MCP exposure, graceful shutdown
+ 591b9d1a8cdcbe37b2baa6e4275cca756d3d52af chore(config): openclaw auto-sorted mac-orchestrator.json (lmstudio-mac models)
+ 48bfa6d934e8c612bebc2a400f35141dc31069c4 arch: ollama first-class priority on Mac (qwen3.5:9b-nvfp4 + LM Studio Win)
+ c3d7463f6826ed2bf7317a0418de165b2fc35639 fix(security): redact committed secrets and harden scanning gates
+ b23483bcf136de77b9b4e150497d19257fb503da feat(omniroute): add full disable/re-enable runbook + local API fallback
+ bd173c815ef2732b586546eb75f784a447a03020 chore(omniroute): mark sidecar DISABLED in SKILL.md (2026-06-14)
+ 8548dbe8c2092709dc7f9eb9bcdb57bcab5b7103 fix(test): move local-api-fallback body to references/ to stay under 500-line gate
```

#### `2026-06-26--dev-recalib-cursor-agent`

```text
+ 431a37d084207b2c899defa3e9d77bb5893cdb01 feat(tdd): 2026-06-26 dev-recalib — Vitest gate, oramasys-method wiring, Hermes prep
+ f5538647b4383315afc9322fd4f0f6c9921bcaa6 fix(windows): normalize gstack-brain-sync.cmd EOL + platform turf policy
```

#### `fix/pr135-lint006-windows`

```text
+ 148c86f8606cbc5d3a1eb2c2a8a839890931312a fix(hygiene): LINT-006 Windows user-profile paths + PR #135 lesson
```

#### `v1.1-oramasys-Fable-5-preparation-part-1`

```text
+ b8c39ddc17dd34bc694b4755fce4a278ed70cd40 feat(start): ollama idempotent startup, per-profile config, MCP exposure, graceful shutdown
+ 591b9d1a8cdcbe37b2baa6e4275cca756d3d52af chore(config): openclaw auto-sorted mac-orchestrator.json (lmstudio-mac models)
+ 48bfa6d934e8c612bebc2a400f35141dc31069c4 arch: ollama first-class priority on Mac (qwen3.5:9b-nvfp4 + LM Studio Win)
+ c3d7463f6826ed2bf7317a0418de165b2fc35639 fix(security): redact committed secrets and harden scanning gates
+ 329d20c1b946e24c55d41e713c91586e90b3b465 docs(distill-fable-5): preserve original pre-autoplan versions in archive (baseline for v1/v2 comparison)
+ cdf120e11c54b981c2767fe518e8cf3b572ab2dc feat(distill-fable-5): v1 CLI complete, Group A kickoff unblocked
+ 0a1972614ea1ae3930fa22f4a0b64402ffc4e67d fix: upgrade esbuild to 0.28.1 (GHSA-gv7w-rqvm-qjhr)
+ c9a9aa4bc41ebdfff19f7f9d9248b682f7741c69 fix: verify_before_done.py --check plan skips task-plan in non-interactive mode
+ 887aa5561e9f0485cfb8867c02c33f321fc99b1a fix: address coderabbit review — non-interactive flag, dir resolution, plan check
+ 9851b1f7a9a30b379b44006ae5fdce66ff0194fd fix: correct fallback chain order — LM Studio Mac is last, not third
```

#### `wip/preserve-local-main-20260614`

```text
+ b8c39ddc17dd34bc694b4755fce4a278ed70cd40 feat(start): ollama idempotent startup, per-profile config, MCP exposure, graceful shutdown
+ 591b9d1a8cdcbe37b2baa6e4275cca756d3d52af chore(config): openclaw auto-sorted mac-orchestrator.json (lmstudio-mac models)
+ 48bfa6d934e8c612bebc2a400f35141dc31069c4 arch: ollama first-class priority on Mac (qwen3.5:9b-nvfp4 + LM Studio Win)
+ c3d7463f6826ed2bf7317a0418de165b2fc35639 fix(security): redact committed secrets and harden scanning gates
+ 329d20c1b946e24c55d41e713c91586e90b3b465 docs(distill-fable-5): preserve original pre-autoplan versions in archive (baseline for v1/v2 comparison)
+ cdf120e11c54b981c2767fe518e8cf3b572ab2dc feat(distill-fable-5): v1 CLI complete, Group A kickoff unblocked
```

#### `wip/vitest-scratch`

```text
+ 85f59051b5705901fd2badd9c78a7e9685593332 wip: vitest scratch + tdd-gate docs (restored from stash 2026-06-26)
```

### Re-anchor only (`+` = 0)

| Branch | Tip | Graft est. | Twin |
|--------|-----|------------|------|
| `rebase-103-local` | `9815ee2` | 1 | `c17e1e924` |
| `rebase-104-local` | `46a05ad` | 1 | `0e082a817` |

### Stale (graft > 10, still has `+`)

- `2026-06-13-001-ac-regression-repair-v2`: graft ~188, `+`=6
- `2026-06-13-001-post-fable5-ac-regression-repair`: graft ~192, `+`=11
- `2026-06-14-001-omniroute-ops-and-local-fallback`: graft ~216, `+`=7
- `2026-06-14-002-omniroute-settings-env-fix`: graft ~216, `+`=7
- `v1.1-oramasys-Fable-5-preparation-part-1`: graft ~191, `+`=10
- `wip/preserve-local-main-20260614`: graft ~187, `+`=6

## Cross-repo PR priority (`+` only)

| P | Repo | Branch | `+` |
|---|------|--------|-----|
| P1 | orama | `2026-06-13-001-post-fable5-ac-regression-repair` | 11 |
| P2 | orama | `v1.1-oramasys-Fable-5-preparation-part-1` | 10 |
| P3 | PT | `fix/pt71-review-v2` | 9 |
| P4 | PT | `fix/ci-71` | 7 |
| P5 | PT | `fix/pt71-onto-main` | 7 |
| P6 | orama | `2026-06-14-001-omniroute-ops-and-local-fallback` | 7 |
| P7 | orama | `2026-06-14-002-omniroute-settings-env-fix` | 7 |
| P8 | PT | `fix/ci-69` | 6 |
| P9 | orama | `2026-06-13-001-ac-regression-repair-v2` | 6 |
| P10 | orama | `wip/preserve-local-main-20260614` | 6 |
| P11 | PT | `2026-06-11-001-win-endpoint-discovery-sync` | 5 |
| P12 | PT | `2026-06-26--dev-recalib-cursor-agent` | 2 |
| P13 | PT | `temp-recovery` | 2 |
| P14 | orama | `2026-06-26--dev-recalib-cursor-agent` | 2 |
| P15 | PT | `chore/domain-knowledge-windows-shims` | 1 |
| P16 | PT | `clean-pt127` | 1 |
| P17 | PT | `recover/2026-05-31-codex-plan-revision` | 1 |
| P18 | orama | `fix/pr135-lint006-windows` | 1 |
| P19 | orama | `wip/vitest-scratch` | 1 |

## Commands

```bash
# Perpetua-Tools
scripts/git/reanchor_scan.sh . origin/main heads
git cherry -v origin/main <tip> <twin-from-scan>

# orama-system
cd ../orama-system && scripts/git/reanchor_scan.sh . origin/main heads
```

