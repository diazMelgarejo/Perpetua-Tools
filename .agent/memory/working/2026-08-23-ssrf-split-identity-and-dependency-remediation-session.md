# SSRF split-identity landing + full dependency-alert remediation (2026-08-23)

**Context:** Continuation of the PT #359 / orama #321 SSRF hardening thread
(see [[2026-08-22-pr359-review-4998833290-deferred-items]] for the prior
session's Deferred #1/#2 framing). This session closed both deferrals, then
widened into a full Dependabot alert reconciliation across PT, orama-system,
and a third-party vendored submodule, ending in a genuine forensic dig into
*why* one dependency alert had silently survived a Dependabot "fix" for two
weeks. Recorded here so the full story doesn't have to be re-derived.

## Timeline

**2026-08-22, ~20:00–21:00** — Split-identity SSRF fix (Deferred #1)
- Synthesized 3 independently-converged designs (own research, Agnes's
  Reference Guide 09, Perplexity's review 09b) into the Split-Identity Rule:
  `host_params["host"] = pinned_ip` (PLACE), `server_hostname`/
  `assert_hostname`/`Host` header = original hostname (NAME).
- Live end-to-end sanity check (`ssrf_request('GET','https://api.github.com/zen')`)
  caught a genuine pre-existing bug: `assert_same_host` is a
  `urlopen()`-only urllib3 parameter, never a valid `Connection`/
  `ConnectionPool.__init__()` kwarg — it had been silently threaded through
  `pool_kwargs` since the adapter's first commit, never caught because every
  prior test mocked either `ssrf_request` itself or pool-level `urlopen`,
  never real connection construction. See [[lesson_37ee7b9f2700]].
- Full 6-test regression matrix (per `references/09b-Perplexity-review.md`
  Part 4 §3) written, RED-GREEN verified via `git stash push --keep-index`
  against pre-fix code — 4/6 fail for the documented reason on old code.
  See [[lesson_aff598036414]].
- Landed as PT commits `351bad1e` (fix) + `5a6a4ae7` (tests). Pushed to
  PR #359.

**2026-08-22, ~20:50–20:57** — Dispatched Agnes on orama docs update
- Queue task `T5-SSRF-orama-layer2-docs-provisional-to-shipped-7a767b81`,
  dispatched via GossipBus + PT distributed queue.
- Agnes completed in ~3 minutes: updated `docs/v2/32-agentic-security-controls.md`
  + `docs/v2/plans/2026-08-20-ssrf-defense-in-depth.md` to "Shipped", then
  went further unprompted and embedded explicit commit SHAs as evidence.
- Independently verified by a dispatched haiku sub-agent (polled the queue +
  GossipBus, diffed the actual orama-system commit content against the PT
  commits it cited) — confirmed honest, no fabrication, no scope creep.
  Landed as orama commits `c841ed31` + `289a6fc7` on PR #321.

**2026-08-23, ~04:44–05:00** — Deferred #2: `orama_bridge.py` loopback routing
- Real bug (not just a CodeRabbit nitpick): `call_oramasys_bridge()` and
  `call_oramasys_mcp_or_bridge()` routed *every* call — including orama's
  own default `ORAMA_ENDPOINT=http://localhost:8001` — through
  `ssrf_request`, whose deny-by-default policy blocks loopback/RFC1918 by
  design. Every real call to orama's default deployment would raise
  `AddressDenied`. Existing tests never caught it — they mocked
  `ssrf_request` entirely, silently absorbing the loopback case (false
  green). See [[lesson_cabdd002df07]].
- Fixed by classifying local (loopback/RFC1918) vs. remote via
  `validate_model_endpoint_url(url, allow_public=False)`, mirroring
  `connectivity.py`'s proven `_probe`/`_probe_local` split. Verified with a
  real local `HTTPServer` (no mocking) end-to-end.
- Landed as PT commit `92259e6f`. Pushed to PR #359.

**2026-08-23, ~05:10–05:30** — Guard-script sync + push both branches
- `orama-system/scripts/git/sync-attribution-guard-scripts.sh` confirmed PT
  already byte-identical to canonical (no action needed).
- Pushed PT (`24bc3490..92259e6f`) and orama-system
  (`06292471..289a6fc7`) — both required `env -u GITHUB_TOKEN` first (a
  stale `GITHUB_TOKEN` env var was shadowing a valid keyring `gh` account).

**2026-08-23, ~05:35–06:15** — Dependabot alert reconciliation
- User asked for a *proactive latest-secure-version* plan, not just the
  minimum patched floor. First research pass hit a `gh api
  dependabot/alerts` 401 (missing `security_events` scope) and fell back to
  an OSV.dev sweep — which found PT's real alert count didn't match (1 OSV
  hit vs. GitHub's reported 8).
- Root cause of the gap: `env -u GITHUB_TOKEN gh api ...` (same env-var fix
  as the push) unblocked the authoritative endpoint. Result: **all 8 PT
  alerts are npm-only** (2× `@hono/node-server`, 3× `ip-address` GHSA-mwp4,
  3× `ip-address` GHSA-4xrf/22jq across `alphaclaw-mcp` + `local-agents`
  manifests) — GitHub's dependency graph doesn't scan PT's `uv.lock`/pip at
  all, which is *why* the separate `click` GHSA (High, found only via OSV)
  was never one of the 8. See [[lesson_b696555249a3]].
- Discovered the 8 alerts were **already fixed** on `fix/pt-standards-convergence-20260818`
  (commit `4ae1d1da`, landed 2026-08-22 before this session even started) —
  but Dependabot only scans `main`, and the branch hadn't merged. Alerts
  will clear on merge, not before.
- Bonus fixes applied directly (user: "keep all on one branch", "reuse
  existing PR for pt and orama" — no new branches, push straight to
  #359/#321):
  - PT: `click` 8.1.8→8.4.2 (latest 8.x, the separate pip-only High finding).
  - PT: `ip-address` in `local-agents` 10.4.0→10.5.0 — already
    vulnerability-free at 10.4.0, bumped purely for latest-version
    consistency with `alphaclaw-mcp` (already 10.5.0).
  - orama: `js-yaml` override `^4.3.0`→`^4.3.1` in `web/pnpm-workspace.yaml`
    (**not** `package.json` — see below).

**2026-08-23, ~06:15–06:25** — pnpm config-location trap
- First attempt added `pnpm.overrides` to `web/package.json` — `pnpm install`
  printed an explicit runtime WARN: *"The pnpm field in package.json is no
  longer read by pnpm... See https://pnpm.io/settings"*. pnpm v9.7+/v11
  moved overrides to a sibling `pnpm-workspace.yaml`. Reverted the no-op
  edit, found the real `overrides:` block there, fixed it correctly. See
  [[lesson_913adf2182d2]].

**2026-08-23, ~06:30–07:00** — Claude-Desktop-LLM (third-party submodule) PR
- `vendor/Claude-Desktop-LLM` (submodule, `yayoboy/Claude-Desktop-LLM`) had
  6 vulnerable transitive npm packages across 3 modules
  (`@modelcontextprotocol/sdk`, `ajv`, `body-parser`, `fast-uri`,
  `path-to-regexp`, `qs`), all pulled in via the SDK's own `^1.0.0` range.
  Per the standing rule (never hand-edit a tracked submodule directly), and
  since our account only had READ access to the upstream repo: forked it
  (`diazMelgarejo/Claude-Desktop-LLM`), branched, ran non-force
  `npm audit fix` in all 3 modules (0 vulnerabilities post-fix, no
  `package.json` ranges touched — confirms non-breaking), pushed, opened
  **https://github.com/yayoboy/Claude-Desktop-LLM/pull/4** against upstream.
  PT's submodule pin is untouched — will bump only once/if that PR merges.

**2026-08-23, ~07:00–07:20** — `web/package-lock.json` forensics (the actual
detective story — the user asked "what actually used it in the first
place?" after the initial fix-in-place attempt was redirected to "just
delete it, it's stale")

The full archaeology, via `git log --diff-filter=A` / `git show --stat` on
`web/package-lock.json` and `web/pnpm-lock.yaml`:

1. **2026-05-20** (`9b9eb20b`) — `web/` created with plain `npm install`.
   `package-lock.json` was the real, actively-consumed lockfile.
2. **2026-06-12** (`5f37488b`) — `"build(web): migrate orama-system/web from
   npm to pnpm (#77)"`. Commit message literally: *"Drop package-lock.json
   in favor of pnpm-lock.yaml; add pnpm-workspace.yaml."* Correctly deleted
   `package-lock.json` (4250 lines removed) and added `pnpm-lock.yaml`
   (2551 lines). `.github/workflows/ci.yml` runs `pnpm install
   --frozen-lockfile` — `pnpm-lock.yaml` has been the sole CI-enforced
   lockfile ever since.
3. **2026-07-13** (`0a2496d2`) — `"feat(kimi-agent): verify and document
   Windows install path (v0.23.6)"` — an UNRELATED kimi-agent Windows-docs
   commit. Its own message admits: *"Also committing web/package-lock.json
   (untracked from a fresh npm install...)"*. Someone ran a plain `npm
   install` in `web/` (likely testing on a machine without pnpm set up),
   and the resulting `package-lock.json` rode along into an otherwise
   unrelated commit — 6221 lines resurrected, never intended to be tracked
   again.
4. **2026-08-08** (`bba9f06c`, `dependabot[bot]`) — `"chore(deps): bump the
   npm_and_yarn group across 1 directory with 2 updates"` (postcss +
   js-yaml). Dependabot's automated npm_and_yarn updater found the
   resurrected `package-lock.json`, assumed npm was canonical for that
   directory, and dutifully "fixed" js-yaml in it. It also touched
   `pnpm-lock.yaml` in the same commit — but only for `postcss` (a normal
   resolved dependency); it could **not** actually bump js-yaml there,
   because js-yaml's version was governed by `pnpm-workspace.yaml`'s
   `overrides:` block (`js-yaml: ^4.3.0`), which Dependabot's PR generator
   doesn't understand or edit. Net effect: a Dependabot PR that *looked*
   like it fixed GHSA-5p4m-2wfm-xmqj, merged clean, closed nothing — the
   real lockfile's pin stayed vulnerable for two more weeks, until this
   session (§ above).
5. **2026-08-23** (this session) — first attempted a targeted js-yaml bump
   in the real file, then (user: "fix: orama's web/package-lock.json is
   stale") deleted `package-lock.json` outright (`fb76ad6e`) rather than
   re-syncing it: confirmed zero references anywhere (no CI job, no script,
   no doc), so nothing consumes it and it can only drift again.

**Root cause, one sentence:** an accidental `npm install` sweeping into an
unrelated commit resurrected a supposedly-deleted lockfile, and Dependabot's
automation then spent a PR "fixing" a file nothing reads — masking, rather
than closing, the real gap. Generalized as [[lesson_5bb056e1a36f]].

## Cross-reference

- Prior session's deferral framing: [[2026-08-22-pr359-review-4998833290-deferred-items]]
- All 6 lessons graduated this session (episodic + semantic, zero
  duplicates verified across 721 records both times):
  [[lesson_aff598036414]] (split-identity rule),
  [[lesson_37ee7b9f2700]] (urlopen-only kwargs),
  [[lesson_cabdd002df07]] (deny-by-default needs opposite-polarity local path),
  [[lesson_b696555249a3]] (Dependabot scans default branch + manifest-type gaps),
  [[lesson_913adf2182d2]] (pnpm-workspace.yaml, not package.json, ≥v9.7),
  [[lesson_5bb056e1a36f]] (stray lockfile masks real Dependabot fixes)
- PT #359: `24bc3490..af3c45de` (7 commits this session)
- orama #321: `06292471..fb76ad6e` (4 commits this session)
- External: `yayoboy/Claude-Desktop-LLM#4` (new fork + PR, non-breaking)
