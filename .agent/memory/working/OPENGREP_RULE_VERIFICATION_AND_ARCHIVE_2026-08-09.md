# Opengrep Rule Verification + `bump-agentic-stack-vendor-pin` Archive — 2026-08-09

**Parent context:** part of the same-day branch-salvage arc
(`CODERABBIT_REMEDIATION_AND_REANCHOR_ARC_2026-08-09.md`). This essay covers
the empirical semgrep verification that decided whether
`bump-agentic-stack-vendor-pin`'s stranded `.opengrep.yml` commit was worth
landing, and what happened to the branch afterward.

## What was being decided

`bump-agentic-stack-vendor-pin` (stranded post-#338-merge commit `0e8149ca`)
touched two rules in `.opengrep.yml`: `pt-bash-unquoted-var` and
`pt-no-hardcoded-secret-env`. `fix/opengrep-rules-and-guard-sync-dedup`
(commit `4db340c5`, already pushed earlier the same day) touched
`pt-bash-unquoted-var` too, with a textually different diff. Rather than
assume they conflicted or that one superseded the other, installed the
actual tool (`uv tool install semgrep`, v1.172.0) and tested both.

## Finding 1 — `pt-bash-unquoted-var`: two correct, convergent solutions

Test sample: 4 lines, `rm -rf "$VAR"` / `rm -rf $VAR` / `rm -rf "${VAR}"` /
`rm -rf ${VAR}` (2 properly quoted, 2 genuinely unquoted).

| Rule version | Lines flagged | Correct? |
|---|---|---|
| Current `origin/main` | 2, 3, 4, 5, 6 (everything, including the assignment line and both quoted lines) | No — badly broken |
| `bump-agentic-stack-vendor-pin` (drops `pattern-not`) | 4, 6 (exactly the 2 unquoted lines) | **Yes** |
| `fix/opengrep-rules-and-guard-sync-dedup` (already pushed) | 4, 6 (exactly the 2 unquoted lines) | **Yes** |

Both fixes are correct. The pushed fix's shape (`pattern: rm -rf ${$VAR}` +
`pattern-not-inside: |` / `"...${$VAR}..."`) turns out to be the *canonical*
form — verbatim from semgrep's own 2021 blog post,
["Scanning Shell Scripts With Semgrep"](https://semgrep.dev/blog/2021/scanning-shell-scripts-with-semgrep/),
which uses this exact rule (catching unquoted shell variable expansion) as
its worked example. `bump-agentic-stack-vendor-pin`'s simpler
drop-the-pattern-not approach also empirically works, but is redundant with
what's already landed. Landing it would add nothing.

## Finding 2 — `pt-no-hardcoded-secret-env`: genuinely broken, on BOTH sides

Test sample: `api_key="sk-abcdefgh12345678"` (real secret, should flag),
`api_key="short"` (too short, should not), `api_key=$DYNAMIC_VALUE` (not a
literal, should not), `normal_var="just a regular string..."` (not a secret
name, should not).

Neither current `origin/main`'s rule nor `bump-agentic-stack-vendor-pin`'s
proposed rewrite matches **any** line — including the textbook positive
case. This isn't a corner-case false negative; the rule is a silent no-op on
both sides.

Root cause, narrowed via targeted debug rules: semgrep's Bash language
support (marked experimental by semgrep's own blog: "many bugs exist") does
not expose quoted strings as a distinct string-literal AST node the way it
does for languages like Python or JS. A bare metavariable captures a quoted
RHS *including the surrounding quote characters* as a generic expression
match (`api_key=$X` matches, `$X` = `"sk-abcdefgh12345678"` quotes and all).
The literal-metavariable quoted syntax (documented as the way to match a
string literal and bind its *inner* content) matches nothing against real
bash — even a fully literal, hardcoded pattern
(`api_key="$VALUE"` against `api_key="sk-..."`) fails to match. Corroborated
by a still-open semgrep GitHub issue (#4117) about `metavariable-pattern`
not capturing full Bash expression content, and the semgrep docs' own note
that literal-metavariable content needs `language: generic` in a nested
`metavariable-pattern` to be re-parsed meaningfully — something neither
rule version does.

**This is a genuinely open bug, not fixed by either branch.** Not patched
in this session — needs dedicated follow-up (most promising direction:
match with a bare metavariable and write the length/shape regex to expect
the surrounding quote characters, rather than assuming they're stripped;
this was tested partially but not landed due to shell/YAML regex-escaping
issues in the test harness itself, not a further tool limitation — worth
picking back up with a cleaner test setup).

**Follow-up research corroboration:** a semgrep blog post about promoting
Kotlin from experimental to GA
<https://semgrep.dev/blog/2023/kotlin-ga/#the-program-analysis-perspective>
explains that `"$X"` is fundamentally *ambiguous* between two
interpretations — (a) a literal double-quoted string node containing an
interpolated metavariable, or (b) the documented literal-metavariable
syntax (match any string literal, bind its content to `$X`) — and semgrep
resolved this per-language as each one matured toward GA, ultimately
picking interpretation (b) for `"$X"` and requiring `"${X}"` for (a).
Bash has never reached GA (still marked experimental in semgrep's own
2021 blog post). The empirical finding here — `"$X"` silently matching
nothing against real bash string assignments — is consistent with Bash
never having received that same per-language disambiguation treatment.
This isn't proof of the exact mechanism, but it's strong, independent
corroboration that the gap is a known class of semgrep language-maturity
issue, not a one-off fluke in this specific rule.

## What happened to the branch

`bump-agentic-stack-vendor-pin` was not merged (nothing left to land — its
one real fix is redundant, its other fix doesn't work). Per explicit
instruction, archived rather than deleted:

- Tag: `archive/2026-08-09/bump-agentic-stack-vendor-pin-0e8149ca`
- SHA: `0e8149ca4991b4c67de57f175f3cdb88b62ec776`
- Pushed to `origin`, annotated with this finding's summary, marked
  never-delete by convention (tags aren't touched by branch-cleanup tooling
  the way branches are).
- The branch ref itself (`bump-agentic-stack-vendor-pin`) was left as-is,
  untouched — the tag is the durable record; renaming or deleting the
  branch risked disturbing whatever still references the old (merged) PR
  #338 by that branch name.

## Related

- [`CODERABBIT_REMEDIATION_AND_REANCHOR_ARC_2026-08-09.md`](CODERABBIT_REMEDIATION_AND_REANCHOR_ARC_2026-08-09.md)
  — parent arc essay
- `lesson_31a635516ea1` — convergent-solutions verification lesson
- `lesson_e8d8ee140589` — semgrep Bash experimental-support silent-no-op lesson
