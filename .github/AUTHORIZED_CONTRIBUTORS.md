# Authorized Contributors

These actors are authorized to author commits and open pull requests in this repository.

| Actor | Type | Email / Identity |
|-------|------|-----------------|
| `cyre` | Human (owner) | `diazMelgarejo@gmail.com`, `Lawrence@cyre.me`, plus configured private owner email |
| `Cursor Agent` | AI assistant | `cursoragent@cursor.com` |
| `Claude` | AI assistant | `noreply@anthropic.com` (any name), `claude@anthropic.com` (name `Claude`) |
| `claude[bot]` | Automation | `claude[bot]@users.noreply.github.com` (the Claude GitHub App; GitHub's `<id>+claude[bot]@…` form matches too) |
| `cline-session-20260907` | AI assistant | `agent@oramasys.local` (fingerprint in `authorized-private-identities.sha256`; authorized by the owner 2026-09-27) |
| `dependabot[bot]` | Automation | `49699333+dependabot[bot]@users.noreply.github.com` |
| `ecc-tools[bot]` | Automation | `257055122+ecc-tools[bot]@users.noreply.github.com` |

## Policy

- The machine-readable source of truth is `scripts/git/identity-policy.json`
  (canonical in orama-system, byte-synced here). `repo_hygiene.py` reads it;
  this table documents it. Only listed addresses are approved, never a whole
  vendor domain, because git author emails are self-asserted.

- Commits authored by the owner use `diazMelgarejo@gmail.com`,
  `Lawrence@cyre.me`, or the configured private owner email kept outside the
  repository.
- A human-authored commit that used Cursor or Claude lists that assistant as
  `Co-authored-by` (`Cursor Agent <cursoragent@cursor.com>` or
  `Claude <noreply@anthropic.com>`), not as the git author.
- A commit authored by an authorized AI assistant uses that assistant's listed
  identity as the git author. `cline-session-20260907` and `Claude` are such
  authors.
  Add a Cursor or Claude `Co-authored-by` trailer only when that assistant
  actually contributed to the commit.
- Legacy/erroneous identity — any message or code commit containing other
  addresses not listed here SHOULD be considered incorrect and rewritten
  before merge.
