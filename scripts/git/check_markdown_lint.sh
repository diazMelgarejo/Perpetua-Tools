#!/usr/bin/env bash
# Preventive markdown gate: lint every STAGED .md file with the same config CI uses
# (.markdownlint-cli2.jsonc, so its ignores apply). Fails closed: if markdownlint-cli2
# is missing the commit is rejected with install instructions, never silently skipped.
# Same script in orama-system and Perpetua-Tools; wired into .githooks/pre-commit.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit 1

mapfile -t FILES < <(git diff --cached --name-only --diff-filter=ACMR -- '*.md')
[ "${#FILES[@]}" -eq 0 ] && exit 0

if command -v markdownlint-cli2 >/dev/null 2>&1; then
  LINT=(markdownlint-cli2)
elif command -v npx >/dev/null 2>&1; then
  LINT=(npx --yes markdownlint-cli2@0.17.2)
else
  echo "check_markdown_lint: markdownlint-cli2 not found." >&2
  echo "  install: npm install -g markdownlint-cli2@0.17.2" >&2
  exit 1
fi

if ! "${LINT[@]}" "${FILES[@]}"; then
  echo "check_markdown_lint: staged markdown violates the CI lint rules (see above)." >&2
  echo "  Rule of thumb: wrap prose at 100 columns (tables, headings, code are exempt)." >&2
  exit 1
fi
