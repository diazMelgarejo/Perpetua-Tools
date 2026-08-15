#!/usr/bin/env bash
# TDD gate for web/src/ — requires a staged *.test.ts(x) when production TS/TSX
# changes are staged, unless the commit message documents tdd-skip: <reason>.
# Canonical policy: docs/TDD.md. Wired from .githooks/commit-msg.
set -euo pipefail

msg_file="${1:-}"

if [[ -n "$msg_file" && -f "$msg_file" ]]; then
  if grep -qE '(^|[[:space:]])tdd-skip:' "$msg_file"; then
    exit 0
  fi
fi

staged=()
while IFS= read -r line; do
  staged+=("$line")
done < <(git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null || true)

prod=()
tests=()
if ((${#staged[@]})); then
  for f in "${staged[@]}"; do
    [[ "$f" == web/src/* ]] || continue
    case "$f" in
      web/src/test/*) continue ;;
      *.test.ts|*.test.tsx) tests+=("$f"); continue ;;
      *.ts|*.tsx) prod+=("$f");;
    esac
  done
fi

if ((${#prod[@]} == 0)); then
  exit 0
fi

# Per-file pairing: each production file must have a test with the same stem
# in the same directory (e.g. Widget.tsx → Widget.test.tsx or Widget.test.ts).
# Allowing "any staged test anywhere" would let an unrelated test satisfy the
# gate for a completely different production file, weakening the TDD contract.
missing=()
for f in "${prod[@]}"; do
  stem="${f%.*}"          # strip final extension: web/src/foo/Widget.tsx → web/src/foo/Widget
  matched=0
  if ((${#tests[@]} > 0)); then
    for t in "${tests[@]}"; do
      if [[ "$t" == "${stem}.test.ts" || "$t" == "${stem}.test.tsx" ]]; then
        matched=1
        break
      fi
    done
  fi
  ((matched)) || missing+=("$f")
done

if ((${#missing[@]} == 0)); then
  exit 0
fi

echo "ERROR: TDD gate — web/src/ production file(s) staged without an adjacent *.test.ts(x)." >&2
printf '  %s\n' "${missing[@]}" >&2
echo "Each changed file needs its own test staged in the same commit (docs/TDD.md)." >&2
echo "To override: add  tdd-skip: <reason>  to the commit message." >&2
exit 1
