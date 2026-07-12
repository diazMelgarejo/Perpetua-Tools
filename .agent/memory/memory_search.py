#!/usr/bin/env python3
"""Opt-in SQLite FTS5 search over tracked memory documents."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
AGENT_ROOT = MEMORY_DIR.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))
from feature_flags import feature_enabled as _shared_feature_enabled  # noqa: E402

INDEX_DIR = MEMORY_DIR / ".index"
INDEX_PATH = INDEX_DIR / "memory.db"
FEATURES_PATH = MEMORY_DIR / ".features.json"
MEMORY_SUFFIXES = (".md", ".jsonl")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
FALLBACK_TIMEOUT_SECONDS = 10


def feature_enabled() -> bool:
    """Return whether the beta memory-search feature is explicitly enabled."""
    return _shared_feature_enabled(FEATURES_PATH, "memory_search_fts")


def _memory_files():
    """Yield tracked memory documents while excluding the generated index."""
    for path in MEMORY_DIR.rglob("*"):
        if ".index" in path.parts:
            continue
        if path.is_file() and path.suffix in MEMORY_SUFFIXES:
            yield path


def check_fts5() -> bool:
    """Return whether this Python SQLite build supports FTS5."""
    try:
        with sqlite3.connect(":memory:") as conn:
            conn.execute("CREATE VIRTUAL TABLE _t USING fts5(c)")
        return True
    except Exception:
        return False


def needs_rebuild() -> bool:
    """Detect a missing, stale, corrupt, or deletion-blind index."""
    if not INDEX_PATH.exists():
        return True
    index_mtime = INDEX_PATH.stat().st_mtime
    current = set()
    for path in _memory_files():
        if path.stat().st_mtime > index_mtime:
            return True
        current.add(str(path.relative_to(MEMORY_DIR)))
    try:
        with sqlite3.connect(INDEX_PATH) as conn:
            indexed = {row[0] for row in conn.execute("SELECT filename FROM memories")}
    except sqlite3.OperationalError:
        return True
    return bool(indexed - current)


def _read_jsonl(path: Path) -> str:
    """Convert valid JSONL rows into searchable text."""
    lines = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        parts = [
            entry.get("action", ""), entry.get("reflection", ""),
            entry.get("detail", ""), entry.get("skill", ""),
        ]
        lines.append(" ".join(part for part in parts if isinstance(part, str) and part))
    return "\n".join(lines)


def build_index() -> int:
    """Rebuild the FTS index and report per-file failures to stderr."""
    INDEX_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(INDEX_PATH) as conn:
        conn.execute("DROP TABLE IF EXISTS memories")
        conn.execute(
            "CREATE VIRTUAL TABLE memories "
            "USING fts5(filename, content, tokenize='porter unicode61')"
        )
        indexed = 0
        for path in _memory_files():
            try:
                content = (
                    path.read_text(encoding="utf-8", errors="replace")
                    if path.suffix == ".md" else _read_jsonl(path)
                )
                conn.execute(
                    "INSERT INTO memories VALUES (?, ?)",
                    (str(path.relative_to(MEMORY_DIR)), content),
                )
                indexed += 1
            except Exception as exc:
                print(f"warning: failed to index {path}: {exc}", file=sys.stderr)
        conn.commit()
    return indexed


def search_fts5(query: str):
    """Search FTS5, falling back to LIKE for syntax and short-CJK cases."""
    if needs_rebuild():
        build_index()
    with sqlite3.connect(INDEX_PATH) as conn:
        try:
            rows = conn.execute(
                "SELECT filename, snippet(memories, 1, '>>>', '<<<', '...', 30) "
                "FROM memories WHERE memories MATCH ? ORDER BY rank",
                (query,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                "SELECT filename, substr(content, 1, 300) FROM memories WHERE content LIKE ?",
                (f"%{query}%",),
            ).fetchall()
        if not rows and CJK_RE.search(query):
            rows = conn.execute(
                "SELECT filename, substr(content, 1, 300) FROM memories WHERE content LIKE ?",
                (f"%{query}%",),
            ).fetchall()
    return rows


def _fallback_command(query, targets):
    """Build a safe external fallback command with an explicit option boundary."""
    if shutil.which("rg"):
        return (["rg", "-li", "--", query, *targets], "ripgrep")
    if shutil.which("grep"):
        return (["grep", "-ril", "--", query, *targets], "grep")
    return (None, None)


def fallback_tool():
    """Return the selected fallback tool name or ``unavailable``."""
    _, tool = _fallback_command("", [])
    return tool or "unavailable"


def search_fallback(query: str):
    """Run bounded rg/grep search and degrade to an empty result on timeout."""
    targets = [str(path) for path in _memory_files()]
    if not targets:
        return []
    command, _ = _fallback_command(query, targets)
    if not command:
        return []
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=FALLBACK_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return []
    files = [line for line in result.stdout.splitlines() if line]
    rows = []
    for filename in files:
        try:
            relative = Path(filename).relative_to(MEMORY_DIR)
        except ValueError:
            continue
        rows.append((relative, f"(match in {Path(filename).name})"))
    return rows


search_grep = search_fallback


def cmd_rebuild():
    """Rebuild the index when FTS5 is available."""
    if not check_fts5():
        print("FTS5 not available — cannot build index.")
        return
    print(f"Index rebuilt: {build_index()} files indexed.")


def cmd_status():
    """Print feature state and active search backend."""
    enabled = feature_enabled()
    print(f"Feature: memory_search_fts [BETA] — {'ENABLED' if enabled else 'DISABLED (beta, opt-in)'}")
    if not enabled:
        print("Enable via: agentic-stack <harness> --reconfigure")
        return
    if not check_fts5():
        print(f"Mode: FALLBACK ({fallback_tool()})")
        return
    if not INDEX_PATH.exists():
        print("Mode: FTS5 (index not built yet — auto-builds on first search)")
        return
    with sqlite3.connect(INDEX_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    print("Mode: FTS5")
    print(f"Index: {count} files indexed ({INDEX_PATH.stat().st_size // 1024} KB)")
    print(f"Location: {INDEX_PATH}")
    print(f"Fallback available: {fallback_tool()}")


def _refuse_disabled():
    print(
        "memory_search [BETA] is disabled — opt-in only.\n"
        "Enable via onboarding: agentic-stack <harness> --reconfigure",
        file=sys.stderr,
    )
    raise SystemExit(2)


def main():
    """CLI entrypoint."""
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: memory_search.py <query>|--rebuild|--status")
        return
    if args[0] == "--status":
        cmd_status()
        return
    if not feature_enabled():
        _refuse_disabled()
    if args[0] == "--rebuild":
        cmd_rebuild()
        return
    query = " ".join(args)
    results = search_fts5(query) if check_fts5() else search_fallback(query)
    mode = "FTS5" if check_fts5() else fallback_tool()
    if not results:
        print(f"No results for: '{query}'  [mode: {mode}]")
        return
    print(f"Results for: '{query}'  [mode: {mode}]\n")
    for filename, snippet in results:
        print(f"  {filename}\n  {snippet}\n")


if __name__ == "__main__":
    main()
