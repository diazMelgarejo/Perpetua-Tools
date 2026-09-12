"""One-shot PR #388 memory enrichment helper; removed after successful use."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "memory" / "semantic" / "DOMAIN_KNOWLEDGE.md"
LESSONS = ROOT / "memory" / "semantic" / "lessons.jsonl"

MARKER = "## Remote Content Integrity in Limited Sandboxes (verified 2026-09-12)"
SECTION = r'''

## Remote Content Integrity in Limited Sandboxes (verified 2026-09-12)

Canonical detailed reference:
`REMOTE_CONTENT_INTEGRITY_AND_LIMITED_WORKSPACE_DOMAIN_KNOWLEDGE_2026-09-12.md`.

Stable facts from the PR #388 incident arc:

- local Git credentials, `gh` CLI authentication, and a connected GitHub App/API
  are separate authority planes; success or failure in one does not establish
  authority in another;
- a partial, sparse, detached, or not-yet-materialized checkout can present
  mass deletions that disappear once the exact remote ref/object is fetched and
  materialized; `git status` describes the checkout, not remote repository truth;
- UTF-8 text should use a complete text transport when available; manual Base64
  chunking requires an explicit producer/decoder contract;
- Base64 maps 3 raw bytes to 4 encoded characters. `12,288 = 4,096 * 3`, so a
  full 12,288-byte raw chunk encodes to 16,384 Base64 characters without
  padding. This is a worked alignment example, not a universal chunk size;
- independently encoded non-final chunks need 3-byte alignment only when their
  encoded forms are concatenated and decoded once. Independently decoded parts
  do not have that requirement;
- displayed tool output, search snippets, or any payload marked truncated are
  not safe byte transports. Prefer Git objects/raw file APIs; otherwise record
  byte offsets, lengths, ordering, expected final size, and expected final hash;
- local validity, write acknowledgement, exact remote-head integrity, and
  merged-destination integrity are four independent facts. Verify each one;
- Git blob identity proves exact file content, while commit identity also
  includes tree/history/metadata. Different commit SHAs can contain identical
  file blobs.

Compact publication mnemonic:
`AUTH -> REF -> BYTES -> PARSE -> REVIEW -> MERGE -> BYTES AGAIN`.
'''

LESSON_SPECS = [
    (
        "Treat local Git credentials, gh CLI authentication, and connected GitHub App/API authorization as separate authority planes; verify the failing plane before rotating credentials or changing transport.",
        "PR #388 directly observed local git push authentication fail while the connected GitHub integration could still read and write the branch. Conflating those planes causes unnecessary credential changes and unsafe transport workarounds.",
        ["remote workspace", "git credentials", "gh cli", "github app", "authentication plane"],
    ),
    (
        "In a partial or not-yet-materialized remote checkout, treat apparent mass deletion as checkout-state ambiguity until the exact remote ref and objects are fetched and materialized; do not repair or publish from git status alone.",
        "A PR #388 follow-up session directly observed a partial/no-checkout worktree report widespread tracked deletions that disappeared after the exact PR ref was fetched and checked out.",
        ["remote workspace", "partial checkout", "git status", "mass deletion", "exact ref"],
    ),
    (
        "Never reconstruct a large tracked file from displayed or truncated tool output; use raw Git/blob/file transport or explicit byte-offset manifests, then verify final byte count and content hash.",
        "Remote-agent output can be excerpted, wrapped, capped, or marked truncated. The PR #388 incident arc showed that per-step success does not prove reconstructed bytes; authoritative raw transport plus final size/hash checks are required.",
        ["remote workspace", "tool output", "truncation", "byte integrity", "content api"],
    ),
]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT.parent, check=True)


def main() -> None:
    text = DOMAIN.read_text(encoding="utf-8")
    if MARKER not in text:
        DOMAIN.write_text(text.rstrip() + SECTION + "\n", encoding="utf-8")

    lesson_text = LESSONS.read_text(encoding="utf-8")
    learn = ROOT / "tools" / "learn.py"
    for claim, rationale, conditions in LESSON_SPECS:
        if f'"claim": "{claim}"' in lesson_text:
            print(f"lesson already present: {claim}")
            continue
        run(
            sys.executable,
            str(learn),
            claim,
            "--rationale",
            rationale,
            "--conditions",
            *conditions,
        )
        lesson_text = LESSONS.read_text(encoding="utf-8")

    run(sys.executable, str(ROOT / "memory" / "render_lessons.py"))
    run(sys.executable, str(ROOT / "memory" / "auto_dream.py"))

    for path in (ROOT / "memory").rglob("*.jsonl"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except Exception as exc:
                raise SystemExit(f"{path}:{number}: {exc}") from exc

    print("PR 388 enrichment + dream complete")


if __name__ == "__main__":
    main()
