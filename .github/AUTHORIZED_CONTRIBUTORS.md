# Authorized Contributors

These actors are authorized to author commits and open pull requests in this repository.

| Actor | Type | Email / Identity |
|-------|------|-----------------|
| `cyre` | Human (owner) | `diazMelgarejo@gmail.com`, `Lawrence@cyre.me`, plus configured private owner email |
| `Cursor Agent` | AI assistant | `cursoragent@cursor.com` |
| `cline-session-20260907` | AI assistant | `agent@oramasys.local` (fingerprint in `authorized-private-identities.sha256`; authorized by the owner 2026-09-27) |
| `dependabot[bot]` | Automation | `49699333+dependabot[bot]@users.noreply.github.com` |
| `ecc-tools[bot]` | Automation | `257055122+ecc-tools[bot]@users.noreply.github.com` |

## Policy

- Commits authored by the owner use `diazMelgarejo@gmail.com`,
  `Lawrence@cyre.me`, or the configured private owner email kept outside the
  repository.
- AI-assisted commits list `Cursor Agent <cursoragent@cursor.com>` or
  `Claude <noreply@anthropic.com>` as `Co-authored-by`, not as git author.
- Legacy/erroneous identity — any message or code commit containing other
  addresses not listed here SHOULD be considered incorrect and rewritten
  before merge.
