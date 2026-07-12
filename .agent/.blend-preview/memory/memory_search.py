#!/usr/bin/env python3
"""Memory Search [BETA] over tracked .agent/memory documents.

Uses SQLite FTS5 when available and a bounded argv-only ripgrep/grep fallback.
The feature remains opt-in through .agent/memory/.features.json.
"""
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
INDEX_DIR = MEMORY_DIR / ".index"
INDEX_PATH = INDEX_DIR / "memory.db"
FEATURES_PATH = MEMORY_DIR / ".features.json"
MEMORY_SUFFIXES = (".md", ".jsonl")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
FALLBACK_TIMEOUT_SECONDS = 10


def feature_enabled() -> bool:
    try:
        data = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return bool((data.get("memory_search_fts") or {}).get("enabled"))


def _memory_files():
    for path in MEMORY_DIR.rglob("*"):
        if ".index" in path.parts:
            continue
        if path.suffix in MEMORY_SUFFIXES and path.is_file():
            yield path


def check_fts5() -> bool:
    try:
        with sqlite3.connect(":memory:") as conn:
            conn.execute("CREATE VIRTUAL TABLE _t USING fts5(c)")
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
        with sqlite3.connect(INDEX_PATH) as conn:
            indexed_rel = {
                row[0] for row in conn.execute("SELECT filename FROM memories")
            }
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
    with sqlite3.connect(INDEX_PATH) as conn:
        conn.execute("DROP TABLE IF EXISTS memories")
        conn.execute(
            """CREATE VIRTUAL TABLE memories
               USING fts5(filename, content, tokenize='porter unicode61')"""
        )
        indexed = 0
        for path in _memory_files():
            try:
                if path.suffix == ".md":
                    content = path.read_text(encoding="utf-8")
                elif path.suffix == ".jsonl":
                    content = _read_jsonl(path)
                else:
                    continue
                conn.execute(
                    "INSERT INTO memories VALUES (?, ?)",
                    (str(path.relative_to(MEMORY_DIR)), content),
                )
                indexed += 1
            except Exception:
                continue
        conn.commit()
    return indexed


def search_fts5(query: str):
    if needs_rebuild():
        build_index()
    with sqlite3.connect(INDEX_PATH) as conn:
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
                "SELECT filename, substr(content, 1, 300) "
                "FROM memories WHERE content LIKE ?",
                (f"%{query}%",),
            ).fetchall()
        if not rows and CJK_RE.search(query):
            rows = conn.execute(
                "SELECT filename, substr(content, 1, 300) "
                "FROM memories WHERE content LIKE ?",
                (f"%{query}%",),
            ).fetchall()
    return rows


def _fallback_command(query, targets):
    """Return an argv-only command; `--` prevents option confusion.

    -F/fixed-strings forces literal keyword matching in both tools — without
    it, rg treats query as a regex and grep as a BRE, so a query containing
    metacharacters (., *, (, [, +, etc.) would silently match unintended
    content instead of the literal keyword, inconsistent with the FTS5
    term-based path this is a fallback for.
    """
    if shutil.which("rg"):
        return (["rg", "-liF", "--", query, *targets], "ripgrep")
    if shutil.which("grep"):
        return (["grep", "-rilF", "--", query, *targets], "grep")
    return (None, None)


def fallback_tool():
    _, tool = _fallback_command("", [])
    return tool or "unavailable"


def search_fallback(query: str):
    """Bounded external fallback restricted to memory document files."""
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
            timeout=FALLBACK_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode not in (0, 1):
        return []
    files = [line for line in result.stdout.splitlines() if line]
    output = []
    for filename in files:
        path = Path(filename)
        try:
            relative = path.relative_to(MEMORY_DIR)
        except ValueError:
            continue
        output.append((relative, f"(match in {path.name})"))
    return output


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
            print("Also: neither rg nor grep on PATH — install ripgrep.")
        return
    if not INDEX_PATH.exists():
        print("Mode: FTS5 (index not built yet — auto-builds on first search)")
        return
    with sqlite3.connect(INDEX_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
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
    raise SystemExit(2)


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
