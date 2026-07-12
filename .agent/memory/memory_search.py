#!/usr/bin/env python3
"""
Memory Search [BETA] — SQLite FTS5 full-text search over .agent/memory/ files.

Indexes all .md and .jsonl files under .agent/memory/ and provides ranked
keyword search. When SQLite FTS5 is not available, falls back to ripgrep
(`rg`) if installed, then to grep. Fallback paths are always restricted
to .md / .jsonl so implementation files never pollute results.

BETA + opt-in: disabled by default. Enable via onboarding
(agentic-stack <harness> --reconfigure) or by setting
    {"memory_search_fts": {"enabled": true}}
in .agent/memory/.features.json.
"""
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
AGENT_DIR = MEMORY_DIR.parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))
from feature_flags import feature_enabled as _feature_enabled  # noqa: E402

INDEX_DIR = MEMORY_DIR / ".index"
INDEX_PATH = INDEX_DIR / "memory.db"
FEATURES_PATH = MEMORY_DIR / ".features.json"
MEMORY_SUFFIXES = (".md", ".jsonl")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
FALLBACK_TIMEOUT_SECONDS = 15


def feature_enabled() -> bool:
    """True iff ``memory_search_fts`` is explicitly enabled."""
    return _feature_enabled(FEATURES_PATH, "memory_search_fts")


def _memory_files():
    for path in MEMORY_DIR.rglob("*"):
        if ".index" in path.parts:
            continue
        if path.suffix in MEMORY_SUFFIXES and path.is_file():
            yield path


def check_fts5() -> bool:
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE _t USING fts5(c)")
        conn.close()
        return True
    except Exception:
        return False


def needs_rebuild() -> bool:
    if not INDEX_PATH.exists():
        return True
    index_mtime = INDEX_PATH.stat().st_mtime
    current_rel = set()
    for path in _memory_files():
        if path.stat().st_mtime > index_mtime:
            return True
        current_rel.add(str(path.relative_to(MEMORY_DIR)))
    try:
        conn = sqlite3.connect(INDEX_PATH)
        indexed_rel = {row[0] for row in conn.execute("SELECT filename FROM memories")}
        conn.close()
    except sqlite3.OperationalError:
        return True
    return bool(indexed_rel - current_rel)


def _read_jsonl(path: Path) -> str:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        parts = [
            entry.get("action", ""),
            entry.get("reflection", ""),
            entry.get("detail", ""),
            entry.get("skill", ""),
        ]
        lines.append(" ".join(part for part in parts if part))
    return "\n".join(lines)


def build_index() -> int:
    INDEX_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(INDEX_PATH)
    conn.execute("DROP TABLE IF EXISTS memories")
    conn.execute(
        "CREATE VIRTUAL TABLE memories "
        "USING fts5(filename, content, tokenize='porter unicode61')"
    )
    indexed = 0
    for path in _memory_files():
        try:
            content = (
                path.read_text(encoding="utf-8")
                if path.suffix == ".md"
                else _read_jsonl(path)
            )
            conn.execute(
                "INSERT INTO memories VALUES (?, ?)",
                (str(path.relative_to(MEMORY_DIR)), content),
            )
            indexed += 1
        except Exception as exc:
            print(f"warning: failed to index {path}: {exc}", file=sys.stderr)
    conn.commit()
    conn.close()
    return indexed


def search_fts5(query: str):
    if needs_rebuild():
        build_index()
    conn = sqlite3.connect(INDEX_PATH)
    try:
        rows = conn.execute(
            """SELECT filename,
                      snippet(memories, 1, '>>>', '<<<', '...', 30)
               FROM memories
               WHERE memories MATCH ?
               ORDER BY rank""",
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
    conn.close()
    return rows


def _fallback_command(query, targets):
    if shutil.which("rg"):
        return (["rg", "-li", "--", query, *targets], "ripgrep")
    if shutil.which("grep"):
        return (["grep", "-ril", query, *targets], "grep")
    return (None, None)


def fallback_tool():
    _, tool = _fallback_command("", [])
    return tool or "unavailable"


def search_fallback(query: str):
    targets = [str(path) for path in _memory_files()]
    if not targets:
        return []
    cmd, _ = _fallback_command(query, targets)
    if not cmd:
        return []
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=FALLBACK_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return []
    files = [path for path in result.stdout.strip().split("\n") if path]
    return [
        (Path(path).relative_to(MEMORY_DIR), f"(match in {Path(path).name})")
        for path in files
    ]


search_grep = search_fallback


def cmd_rebuild():
    if not check_fts5():
        print("FTS5 not available — cannot build index.")
        return
    print(f"Index rebuilt: {build_index()} files indexed.")


def cmd_status():
    enabled = feature_enabled()
    tag = "ENABLED" if enabled else "DISABLED (beta, opt-in)"
    print(f"Feature: memory_search_fts [BETA] — {tag}")
    if not enabled:
        print("Enable via: agentic-stack <harness> --reconfigure")
        print("Or edit .agent/memory/.features.json directly.")
        return
    if not check_fts5():
        tool = fallback_tool()
        print(f"Mode: FALLBACK ({tool})")
        print("Reason: SQLite FTS5 not available in this Python build.")
        if tool == "unavailable":
            print("Also: neither rg nor grep on PATH — install ripgrep for best results.")
        return
    if not INDEX_PATH.exists():
        print("Mode: FTS5 (index not built yet — auto-builds on first search)")
        return
    conn = sqlite3.connect(INDEX_PATH)
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    conn.close()
    size_kb = INDEX_PATH.stat().st_size // 1024
    print("Mode: FTS5")
    print(f"Index: {count} files indexed ({size_kb} KB)")
    print(f"Location: {INDEX_PATH}")
    print(f"Fallback available: {fallback_tool()}")


def _refuse_disabled():
    print(
        "memory_search [BETA] is disabled — opt-in only.\n"
        "Enable via onboarding:  agentic-stack <harness> --reconfigure\n"
        "Or set enabled=true for memory_search_fts in "
        ".agent/memory/.features.json",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage [BETA, opt-in]:")
        print("  memory_search.py <query>     Search memories by keyword")
        print("  memory_search.py --rebuild   Force rebuild index")
        print("  memory_search.py --status    Show index status")
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
    if check_fts5():
        results = search_fts5(query)
        mode = "FTS5"
    else:
        results = search_fallback(query)
        mode = fallback_tool()
    if not results:
        print(f"No results for: '{query}'  [mode: {mode}]")
        return
    print(f"Results for: '{query}'  [mode: {mode}]\n")
    for filename, snippet in results:
        print(f"  {filename}")
        print(f"  {snippet}\n")


if __name__ == "__main__":
    main()
