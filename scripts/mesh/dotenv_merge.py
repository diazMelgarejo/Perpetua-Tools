"""Integrative dotenv harmonization — fill missing/empty keys only; never delete."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_KEY_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _is_empty_value(raw: str) -> bool:
    value = raw.strip()
    if not value:
        return True
    if value.startswith(('"', "'")) and value.endswith(('"', "'")) and len(value) >= 2:
        return not value[1:-1].strip()
    return False


def _duplicate_comment(line: str) -> str:
    return f"# duplicate (inactive; effective declaration follows): {line.strip()}"


def _superseded_comment(line: str, *, timestamp: str) -> str:
    return f"# superseded {timestamp}: {line.strip()}"


def _managed_line_indices(lines: list[str], keys: frozenset[str]) -> dict[str, list[int]]:
    indices: dict[str, list[int]] = defaultdict(list)
    for index, line in enumerate(lines):
        match = _KEY_LINE_RE.match(line)
        if match and match.group(1) in keys:
            indices[match.group(1)].append(index)
    return indices


def _unquote_dotenv_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith(('"', "'")) and value.endswith(('"', "'")) and len(value) >= 2:
        return value[1:-1].strip()
    return value


def read_dotenv_key(path: Path, key: str) -> str:
    """Return the effective (last) non-empty value for ``key`` in a dotenv file."""
    if not path.is_file():
        return ""
    last = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _KEY_LINE_RE.match(line)
        if match and match.group(1) == key:
            candidate = _unquote_dotenv_value(match.group(2))
            if candidate:
                last = candidate
    return last


def harmonize_dotenv_keys(
    path: Path,
    values: dict[str, str],
    *,
    managed_keys: frozenset[str] | None = None,
    header_comment: str | None = None,
    replace_keys: frozenset[str] | None = None,
    supersede_timestamp: str | None = None,
) -> list[str]:
    """Merge managed keys into a dotenv file without removing comments or existing values."""
    keys = managed_keys if managed_keys is not None else frozenset(values)
    rotate = replace_keys or frozenset()
    pending = {k: v for k, v in values.items() if k in keys and v}
    touched: list[str] = []
    ts = supersede_timestamp or datetime.now(timezone.utc).isoformat()

    if not path.is_file():
        lines: list[str] = []
        if header_comment:
            lines.extend(header_comment.splitlines())
            if lines and lines[-1] != "":
                lines.append("")
        for key in sorted(pending):
            lines.append(f"{key}={pending.pop(key)}")
            touched.append(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return touched

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    managed_indices = _managed_line_indices(lines, keys)
    seen: set[str] = set()
    out: list[str] = []

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        match = _KEY_LINE_RE.match(line)
        if not match:
            out.append(line)
            continue
        key, raw_value = match.group(1), match.group(2)
        if key not in keys:
            out.append(line)
            continue

        key_indices = managed_indices.get(key, [index])
        is_effective = index == key_indices[-1]
        if not is_effective:
            if not stripped.startswith("# duplicate (inactive"):
                out.append(_duplicate_comment(line))
            else:
                out.append(line)
            seen.add(key)
            continue

        seen.add(key)
        if key in pending and key in rotate:
            new_value = pending.pop(key)
            if not _is_empty_value(raw_value):
                out.append(_superseded_comment(line, timestamp=ts))
            out.append(f"{key}={new_value}")
            touched.append(key)
            continue

        if key in pending and _is_empty_value(raw_value):
            out.append(f"{key}={pending.pop(key)}")
            touched.append(key)
        else:
            out.append(line)
            if key in pending:
                pending.pop(key)

    if pending:
        if out and out[-1] != "":
            out.append("")
        if header_comment and not any(header_comment.splitlines()[0] in ln for ln in out):
            out.extend(header_comment.splitlines())
        for key in sorted(pending):
            out.append(f"{key}={pending[key]}")
            touched.append(key)

    new_text = "\n".join(out) + ("\n" if out else "")
    if new_text != original:
        path.write_text(new_text, encoding="utf-8")
    return touched
