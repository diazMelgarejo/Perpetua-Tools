#!/usr/bin/env python3
"""Memory Search [BETA] — opt-in search over tracked memory documents.

Responsibilities:
  1. Index only tracked `.md` and `.jsonl` memory documents.
  2. Prefer SQLite FTS5 when the local Python build supports it.
  3. Fall back to ripgrep, then grep, without searching implementation files.
  4. Rebuild when the index is missing, stale, corrupt, or contains deleted paths.
  5. Surface per-file indexing failures instead of silently hiding blind spots.
  6. Bound external fallback execution so a hung search process cannot block agents.

Feature contract:
  - Disabled by default; enable `memory_search_fts` in `.agent/memory/.features.json`.
  - `--status` remains available while disabled so operators can inspect the mode.
  - Text reads use explicit UTF-8 with replacement decoding for damaged legacy rows.
  - Fallback queries use an option boundary and return an empty result on timeout.

Usage:
  python3 memory_search.py <query>
  python3 memory_search.py --rebuild
  python3 memory_search.py --status
"""
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
INDEX_VERSION = 3


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
            if conn.execute("PRAGMA user_version").fetchone()[0] != INDEX_VERSION:
                return True
            indexed = {row[0] for row in conn.execute("SELECT filename FROM memories")}
    except sqlite3.OperationalError:
        return True
    # Symmetric difference: catch BOTH directions of drift — indexed rows
    # whose files were deleted, AND filesystem files never indexed (e.g. an
    # index rebuilt from a narrower _memory_files() glob in an older run,
    # or a file written with an mtime <= index_mtime due to clock skew /
    # same-tick creation, which the mtime fast-path above cannot detect).
    return bool(indexed ^ current)


def _read_jsonl(path: Path) -> str:
    """Convert valid JSONL rows into searchable text."""
    lines = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        parts = [
            entry.get("action", ""), entry.get("reflection", ""),
            entry.get("detail", ""), entry.get("skill", ""),
        ]
        lines.append(" ".join(part for part in parts if isinstance(part, str) and part))
    return "\n".join(lines)


def _current_lesson_texts(path: Path) -> list[str]:
    """Return latest structured lesson claims with their explicit lifecycle state."""
    latest: dict[str, dict] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.strip():
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]:
                latest[entry["id"]] = entry
    superseded = {row.get("supersedes") for row in latest.values()
                  if row.get("status") == "accepted" and isinstance(row.get("supersedes"), str)}
    return [f"[{'SUPERSEDED' if key in superseded else str(row.get('status', 'unknown')).upper()}] {row.get('claim', '')}"
            for key, row in latest.items()]


def _make_snippet(text: str, query: str, window: int = 150) -> str:
    """Return a bounded snippet around the first matching term."""
    lower = text.casefold()
    pos = -1
    for term in query.casefold().split():
        p = lower.find(term)
        if p != -1 and (pos == -1 or p < pos):
            pos = p
    if pos == -1:
        return text[:window] + "..." if len(text) > window else text
    # A casefolded character may expand to multiple code points (e.g. ß).
    offset = 0
    for original_pos, char in enumerate(text):
        offset += len(char.casefold())
        if offset > pos:
            pos = original_pos
            break
    start = max(0, pos - 40)
    end = min(len(text), pos + window)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def _lesson_preamble(path: Path) -> str:
    """Return the hand-curated section preceding the generated lesson view."""
    content = path.read_text(encoding="utf-8", errors="replace")
    sentinel = "## Auto-promoted entries will be appended below"
    return content.split(sentinel, 1)[0] if sentinel in content else ""


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
                if path.relative_to(MEMORY_DIR).as_posix() == "semantic/LESSONS.md":
                    source = path.with_name("lessons.jsonl")
                    lesson_texts = _current_lesson_texts(source) if source.exists() else []
                    if lesson_texts:
                        preamble = _lesson_preamble(path)
                        try:
                            conn.execute("SAVEPOINT lessons_file")
                            for content in [preamble, *lesson_texts]:
                                conn.execute("INSERT INTO memories VALUES (?, ?)",
                                             (str(path.relative_to(MEMORY_DIR)), content))
                            conn.execute("RELEASE lessons_file")
                            indexed += 1
                            continue
                        except Exception as exc:
                            conn.execute("ROLLBACK TO lessons_file")
                            conn.execute("RELEASE lessons_file")
                            print(f"warning: failed to index {path}: {exc}", file=sys.stderr)
                            continue
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
        conn.execute(f"PRAGMA user_version = {INDEX_VERSION}")
        conn.commit()
    return indexed


def search_fts5(query: str):
    """Search FTS5, falling back to LIKE for syntax and short-CJK cases."""
    if needs_rebuild():
        build_index()
    with sqlite3.connect(INDEX_PATH) as conn:
        try:
            rows = conn.execute(
                "SELECT filename, CASE WHEN filename = 'semantic/LESSONS.md' AND substr(content, 1, 1) = '[' "
                "THEN content ELSE snippet(memories, 1, '>>>', '<<<', '...', 30) END "
                "FROM memories WHERE memories MATCH ? ORDER BY rank",
                (query,),
            ).fetchall()
        except sqlite3.OperationalError:
            terms = query.split()
            if terms:
                where_clause = " AND ".join(["content LIKE ?" for _ in terms])
                params = [f"%{t}%" for t in terms]
                rows = conn.execute(
                    f"SELECT filename, CASE WHEN filename = 'semantic/LESSONS.md' AND substr(content, 1, 1) = '[' "
                    f"THEN content ELSE substr(content, 1, 300) END FROM memories WHERE {where_clause}",
                    params,
                ).fetchall()
            else:
                rows = []
        if not rows and CJK_RE.search(query):
            terms = query.split()
            if terms:
                where_clause = " AND ".join(["content LIKE ?" for _ in terms])
                params = [f"%{t}%" for t in terms]
                rows = conn.execute(
                    f"SELECT filename, CASE WHEN filename = 'semantic/LESSONS.md' AND substr(content, 1, 1) = '[' "
                    f"THEN content ELSE substr(content, 1, 300) END FROM memories WHERE {where_clause}",
                    params,
                ).fetchall()
            else:
                rows = []
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
    semantic = MEMORY_DIR / "semantic"
    source = semantic / "lessons.jsonl"
    markdown = semantic / "LESSONS.md"
    lesson_texts = _current_lesson_texts(source) if (source.exists() and markdown.exists()) else []
    structured = bool(lesson_texts)
    targets = [str(path) for path in _memory_files()
               if not (structured and path in (source, markdown))]
    rows = []
    original_terms = query.split()
    query_terms = [t.casefold() for t in original_terms]
    if structured and query_terms:
        preamble = _lesson_preamble(markdown)
        if all(term in preamble.casefold() for term in query_terms):
            rows.append((Path("semantic/LESSONS.md"), _make_snippet(preamble, query)))
        rows.extend((Path("semantic/LESSONS.md"), content)
                    for content in lesson_texts
                    if all(term in content.casefold() for term in query_terms))
    if not targets or not query_terms:
        return rows
    current_targets = list(targets)
    for term in original_terms:
        command, _ = _fallback_command(term, current_targets)
        if not command:
            return rows
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
            return rows
        matching = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not matching:
            return rows
        current_targets = matching
    for filename in current_targets:
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
        count = conn.execute("SELECT COUNT(DISTINCT filename) FROM memories").fetchone()[0]
    print("Mode: FTS5")
    print(f"Index: {count} files indexed ({INDEX_PATH.stat().st_size // 1024} KB)")
    print(f"Location: {INDEX_PATH}")
    print(f"Fallback available: {fallback_tool()}")


def _refuse_disabled():
    """Explain the opt-in requirement and exit unsuccessfully."""
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
