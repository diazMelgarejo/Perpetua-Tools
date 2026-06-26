#!/usr/bin/env python3
"""One-shot scrub of workstation paths in tracked .agent/memory artifacts.

Re-sanitizes episodic rows, lessons.jsonl, and candidate JSON in place, then
re-renders LESSONS.md. Safe to re-run (idempotent on already-clean text).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEMORY = os.path.join(BASE, "memory")
sys.path.insert(0, MEMORY)

from path_hygiene import sanitize_json_strings  # noqa: E402
from render_lessons import render_lessons  # noqa: E402


def _scrub_jsonl(path: str) -> int:
    if not os.path.isfile(path):
        return 0
    changed = 0
    out_lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            if not raw.strip():
                out_lines.append(raw)
                continue
            row = json.loads(raw)
            clean = sanitize_json_strings(row)
            if clean != row:
                changed += 1
            out_lines.append(json.dumps(clean, ensure_ascii=False))
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + ("\n" if out_lines else ""))
    return changed


def _scrub_candidate_tree(root: str) -> int:
    changed = 0
    if not os.path.isdir(root):
        return 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith(".json"):
                continue
            path = os.path.join(dirpath, fname)
            with open(path, encoding="utf-8") as f:
                row = json.load(f)
            clean = sanitize_json_strings(row)
            if clean == row:
                continue
            with open(path, "w", encoding="utf-8") as f:
                json.dump(clean, f, indent=2)
                f.write("\n")
            changed += 1
    return changed


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--render",
        action="store_true",
        default=True,
        help="Re-render semantic/LESSONS.md after scrub (default: on).",
    )
    p.add_argument("--no-render", action="store_true", help="Skip LESSONS.md render.")
    args = p.parse_args()

    episodic = os.path.join(MEMORY, "episodic", "AGENT_LEARNINGS.jsonl")
    lessons = os.path.join(MEMORY, "semantic", "lessons.jsonl")
    candidates = os.path.join(MEMORY, "candidates")

    n_epi = _scrub_jsonl(episodic)
    n_less = _scrub_jsonl(lessons)
    n_cand = _scrub_candidate_tree(candidates)
    print(f"scrubbed episodic lines: {n_epi}")
    print(f"scrubbed lesson lines: {n_less}")
    print(f"scrubbed candidate files: {n_cand}")

    if args.render and not args.no_render:
        semantic = os.path.join(MEMORY, "semantic")
        render_lessons(semantic)
        print(f"re-rendered: {os.path.join(semantic, 'LESSONS.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
