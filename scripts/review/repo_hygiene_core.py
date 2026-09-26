#!/usr/bin/env python3
"""Repo hygiene guard for Perpetua-Tools.

Checks run in CI and as a pre-commit gate. Mirrors the equivalent script in
orama-system/scripts/review/repo_hygiene.py — keep constants in sync.
"""
from __future__ import annotations

import argparse
import fnmatch
import ipaddress
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


APPROVED_IDENTITIES = {
    ("cyre", "Lawrence@cyre.me"),
    ("cyre", "diazMelgarejo@gmail.com"),
    ("Codex", "codex@openai.com"),
}
# Keep in sync with scripts/git/check_identity.sh (local hooks + pre-commit).
FORBIDDEN_TOKENS = (
    "Lawrence " + "Melgarejo",
    "Lawrence" + "@bettermind.ph",
)
IDENTITY_DOC_EXCEPTIONS: set[str] = {
    ".mailmap",
    # Identity-allowlist artifacts: operator-approved identities belong here by design.
    "scripts/git/audit_attribution.sh",
    "scripts/git/audit_engine.py",
    "scripts/git/check_identity.sh",
    "scripts/git/identity-policy.json",
    "scripts/git/identity-policy.schema.json",
    # Identity-policy unit tests reference approved policy emails by design.
    "tests/test_audit_engine.py",
}
# Personal-path leak protection (OpSec) — block any tracked file from containing
# an absolute path under /Users/<anything>/ or /home/<anything>/. Developer
# workstation paths in public docs are a dox risk and hurt portability.
# Use ~, $REPO_ROOT, or <workspace> instead.
PERSONAL_PATH_PATTERN = re.compile(
    r"(?:/Users/|/home/)([A-Za-z][A-Za-z0-9._-]+)/"
    r"|C:\\Users\\([^\\\"\s]+)\\?",  # capture group so PLACEHOLDERS allowlist works
    re.IGNORECASE,
)
# Username segments that are documentation placeholders, not real leaks.
PERSONAL_PATH_PLACEHOLDERS = frozenset({
    "you", "user", "example", "username", "name", "youruser", "yourname",
    "<user>", "<username>", "USERNAME", "USER",
    "youruser",
})
PERSONAL_PATH_EXCEPTIONS = {
    # The script itself names the pattern in source as documentation.
    "scripts/review/repo_hygiene.py",
    # Hygiene test asserts the rule against fixture content.
    "tests/test_repo_hygiene.py",
    # path_hygiene unit tests use /Users/alice, /home/bob as test fixtures —
    # the file exists specifically to verify the scrubber catches these patterns.
    "tests/test_path_hygiene.py",
    "tests/test_path_hygiene_identity_scrub.py",
}
# Files that legitimately name a topology-fragment pattern (e.g. "/tmp/") in
# their own source as documentation or as the regex definition itself, not
# as a leaked path. Same rationale as PERSONAL_PATH_EXCEPTIONS above --
# a rule that defines a pattern necessarily contains that pattern's text.
TOPOLOGY_TOKEN_EXCEPTIONS = {
    ".agent/memory/path_hygiene.py",
    "tests/test_path_hygiene.py",
}
# Hidden / bidirectional Unicode controls — Trojan-Source defense (CVE-2021-42574).
# These can hide malicious code in diffs. Block in all tracked files except the
# hygiene script and its tests, which name the codepoints for documentation.
BIDI_CONTROL_CHARS = {
    "‪": "LRE", "‫": "RLE", "‬": "PDF",
    "‭": "LRO", "‮": "RLO",
    "⁦": "LRI", "⁧": "RLI", "⁨": "FSI", "⁩": "PDI",
}
BIDI_CONTROL_EXCEPTIONS = {
    "scripts/review/repo_hygiene.py",
    "tests/test_repo_hygiene.py",
}
# Mojibake (LINT-007): UTF-8 text mis-decoded as cp1252/latin-1 then re-saved.
# Build by codepoint so this file contains no literal mojibake to self-trip on.
_CP1252_HIGH_PUNCT = (
    (0x2013, 0x2014),
    (0x2018, 0x201E),
    (0x2020, 0x2022),
    (0x0152, 0x0153),
    (0x0160, 0x0161),
    (0x0178, 0x0178),
    (0x017D, 0x017E),
    (0x0192, 0x0192),
    (0x02C6, 0x02C6),
    (0x02DC, 0x02DC),
)
_CP1252_HIGH_SINGLE = (0x2026, 0x2030, 0x2039, 0x203A, 0x20AC, 0x2122)
_MOJIBAKE_2BYTE = (
    "["
    + chr(0x00C2)
    + "-"
    + chr(0x00EF)
    + "](?:["
    + chr(0x0080)
    + "-"
    + chr(0x00BF)
    + "]|["
    + "".join(
        chr(cp)
        for start, end in _CP1252_HIGH_PUNCT
        for cp in range(start, end + 1)
    )
    + "".join(chr(cp) for cp in _CP1252_HIGH_SINGLE)
    + "])"
)
# Supplementary-plane UTF-8 mis-decoded as latin-1/cp1252 (lead bytes U+00F0–U+00F4).
# Second-byte ranges tightened per RFC 3629 §4:
#   \xF0 → 2nd byte 0x90-0xBF   (U+10000–U+3FFFF)
#   \xF1-\xF3 → 2nd byte 0x80-0xBF  (U+40000–U+FFFFF)
#   \xF4 → 2nd byte 0x80-0x8F   (U+100000–U+10FFFF)
# This prevents false positives like \xF0\x80\x80\x80 (overlong encoding).
_CONT = (
    "(?:["
    + chr(0x0080)
    + "-"
    + chr(0x00BF)
    + "]|["
    + "".join(
        chr(cp)
        for start, end in _CP1252_HIGH_PUNCT
        for cp in range(start, end + 1)
    )
    + "".join(chr(cp) for cp in _CP1252_HIGH_SINGLE)
    + "])"
)
# cp1252 decode of UTF-8 bytes 0x91-0x9F (0x90 stays U+0090 in latin-1 range).
_CP1252_91_9F = (
    0x2018,
    0x2019,
    0x201C,
    0x201D,
    0x2022,
    0x2013,
    0x2014,
    0x02DC,
    0x2122,
    0x0161,
    0x203A,
    0x0153,
    0x017E,
    0x0178,
)
_SECOND_F0 = (
    "(?:["
    + chr(0x0090)
    + "-"
    + chr(0x00BF)
    + "]|["
    + "".join(chr(cp) for cp in _CP1252_91_9F)
    + "])"
)
_MOJIBAKE_4BYTE = (
    "(?:"
    + chr(0x00F0) + _SECOND_F0 + _CONT + _CONT
    + "|[" + chr(0x00F1) + "-" + chr(0x00F3) + "]" + _CONT + _CONT + _CONT
    + "|" + chr(0x00F4) + "[" + chr(0x0080) + "-" + chr(0x008F) + "]" + _CONT + _CONT
    + ")"
)
MOJIBAKE_RE = re.compile(_MOJIBAKE_2BYTE + "|" + _MOJIBAKE_4BYTE)
PRIVATE_GENERATED_TRACKED = {".env", ".env.local", ".paths"}
SECRET_PATTERN_EXCEPTIONS = {
    "packages/alphaclaw-mcp/tests/path-boundary-mcp.test.mjs",
    "packages/local-agents/tests/path-boundary.test.cjs",
    "scripts/review/repo_hygiene.py",
    "tests/test_control_plane_security.py",
    "tests/test_repo_hygiene.py",
}
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "google_api_key",
        re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
        "Google API key (AIza...)",
    ),
    (
        "telegram_bot_token",
        re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
        "Telegram bot token (bot_id:secret)",
    ),
    (
        "github_pat",
        re.compile(r"\bghp_[0-9A-Za-z]{20,}\b"),
        "GitHub personal access token",
    ),
    (
        "openai_api_key",
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        "OpenAI API key",
    ),
    (
        "anthropic_api_key",
        re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
        "Anthropic API key",
    ),
    (
        "aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "AWS access key ID (AKIA...)",
    ),
    (
        "private_key",
        re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----"),
        "Private key block",
    ),
)
SECRET_PLACEHOLDER_MARKERS = (
    "${env:",
    "${ENV:",
    "<YOUR_",
    "<your_",
    "REPLACE_ME",
    "CHANGEME",
    "xxx",
)
# Paths exempt from GENERATED_ARTIFACT_PATTERNS.
# Use sparingly — only for intentionally committed compiled outputs that are
# required for distribution without a build step (e.g., npm MCP packages).
GENERATED_ARTIFACT_EXCEPTIONS: frozenset[str] = frozenset({
    # alphaclaw-mcp pre-built JS — committed so the MCP server installs without
    # requiring `npm run build`. Keep this entry as long as the package is
    # distributed as a pre-built artifact.
    "packages/alphaclaw-mcp/build/index.js",
    "packages/alphaclaw-mcp/build/is-direct-execution.js",
})
VERBOTEN_LITERALS_FILE = ".verboten-literals.local"
EMAIL_LITERAL_RE = re.compile(
    r"(?<![\w.+-])"
    r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"(?![\w.-])"
)
AGENT_EMAIL_LITERAL_ALLOWED_DOMAINS = frozenset({
    "openai.com",
    "anthropic.com",
    "cursor.com",
    "cursor.sh",
    "google.com",
    "google.dev",
    "github.com",
    "microsoft.com",
    "azure.com",
    "perplexity.ai",
    "x.ai",
    "coderabbit.ai",
    "mistral.ai",
    "deepseek.com",
    "cohere.com",
    "meta.com",
    "sourcegraph.com",
    "devin.ai",
    "codeium.com",
    "kimi.ai",
    "cline.bot",
    # RFC 2606 / documentation fixtures only. Do not add personal mail domains.
    "example.invalid",
    "example.com",
    "example.org",
    "example.net",
    "localhost",
})
# RFC 1918 private IPv4 ranges — graduated lesson candidates may contain
# these as operational evidence (e.g. DHCP drift, LAN peer addresses).
# Exempt ONLY .agent/memory/candidates/graduated/*.json from topology-token
# scanning for these patterns; all other .agent guards remain in force.
_RFC1918_PRIVATE_IP_RE = re.compile(
    r"(?:"
    r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"          # 10.0.0.0/8
    r"|\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"  # 172.16-31.0.0/12
    r"|\b192\.168\.\d{1,3}\.\d{1,3}\b"          # 192.168.0.0/16
    r")"
)
# Staged-diff gate. Same classes the SSRF dialer denies in
# src/utils/ssrf_pinned_adapter.py `_DENIED_NETWORKS` for these families:
# RFC1918, IPv4/IPv6 loopback, ULA (fc00::/7), and CGNAT (100.64.0.0/10).
# Checked on added index lines only, so unstaged local overlay drift is ignored.
_PROHIBITED_RFC1918_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)
_PROHIBITED_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")
_PROHIBITED_ULA_NET = ipaddress.ip_network("fc00::/7")
_PROHIBITED_ADDRESS_SCAN_EXCEPTIONS = frozenset({
    "scripts/review/repo_hygiene.py",
    "scripts/review/repo_hygiene_core.py",
    "tests/test_repo_hygiene.py",
    "tests/test_repo_hygiene_private_ranges.py",
})
# Candidate extraction only. Classification uses ipaddress.ip_address so a
# partial IPv6 grammar cannot drop compressed forms, and a trailing colon
# (IPv4 port) cannot hide the host. Bracketed literals keep an optional port.
_STAGED_ADDRESS_TOKEN_RE = re.compile(
    r"(?i)(?<![\w:])(?:"
    r"\[[0-9a-f:.]+\](?::\d+)?"
    r"|::ffff:(?:\d{1,3}\.){3}\d{1,3}"
    r"|(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?"
    r"|(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}"
    r")(?![\w])"
)
_HUNK_NEW_START_RE = re.compile(r"\+(\d+)(?:,\d+)?")
GENERATED_ARTIFACT_PATTERNS = (
    ".DS_Store",
    "*/.DS_Store",
    "._*",
    "*/._*",
    "__pycache__/*",
    "*/__pycache__/*",
    "*.pyc",
    "*.pyo",
    ".pytest_cache/*",
    "*/.pytest_cache/*",
    ".mypy_cache/*",
    "*/.mypy_cache/*",
    "dist/*",
    "*/dist/*",
    "build/*",
    "*/build/*",
    "DerivedData/*",
    "*/DerivedData/*",
    "*.egg-info/*",
    "*.whl",
    "*.tar.gz",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.duckdb",
    "*.lmdb",
    "*.mdb",
    "*.har",
    "*.webm",
    "*.mp4",
    "*.log",
    "logs/*",
    "data/*",
    "runtime/*",
    "state/*",
    "sessions/*",
    "screenshots/*",
    "captures/*",
    "ui-captures/*",
    "recordings/*",
    "playwright-report/*",
    "test-results/*",
    "*.xcuserstate",
    "*.xcscmblueprint",
    "*.xcodeproj/xcuserdata/*",
    "*.xcworkspace/xcuserdata/*",
    "*.xcuserdatad/*",
)
WORKFLOW_WRITE_MARKERS = (
    "softprops/action-gh-release",
    "peter-evans/create-pull-request",
    "gh pr",
    "gh release",
    "git push",
)


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    git_exe = shutil.which("git") or shutil.which("git.cmd") or "git"
    return subprocess.run(
        [git_exe, "-C", str(root), *args],
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def openclaw_workspace_root(root: Path) -> Path:
    for candidate in (root, *root.parents):
        if (candidate / "orama-system").is_dir():
            return candidate
    return root


def private_literal_values(root: Path, key: str) -> list[str]:
    configured_path = os.getenv("OPENCLAW_VERBOTEN_LITERALS")
    path = Path(configured_path) if configured_path else openclaw_workspace_root(root) / VERBOTEN_LITERALS_FILE
    if not path.is_file():
        return []
    values: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for raw in lines:
        raw = raw.split("#", 1)[0].strip()
        if not raw or "=" not in raw:
            continue
        raw_key, value = raw.split("=", 1)
        if raw_key.strip() != key:
            continue
        value = value.strip()
        if value:
            values.append(value)
    return values


def local_topology_fragments(root: Path) -> list[str]:
    """Load concrete local path/topology fragments from the local-only registry.

    The repository may describe the invariant, but must not hardcode the
    literal path fragments it bans from memory. Operators keep those fragments
    beside the other off-repo verboten values, using keys such as
    local_path_fragment, local_workspace_fragment, or verboten_path_fragment.
    """
    fragments: list[str] = []
    for key in ("local_path_fragment", "local_workspace_fragment", "verboten_path_fragment"):
        fragments.extend(private_literal_values(root, key))
    return fragments


def tracked_files(root: Path) -> list[str]:
    proc = run_git(root, "ls-files")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git ls-files failed")
    return [line for line in proc.stdout.splitlines() if line]


def is_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return True
    return b"\0" in chunk


def scan_forbidden_identity(root: Path, files: list[str]) -> list[str]:
    errors: list[str] = []
    for rel in files:
        if rel in IDENTITY_DOC_EXCEPTIONS:
            continue
        path = root / rel
        if not path.is_file() or is_binary(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token in FORBIDDEN_TOKENS:
            if token in text:
                errors.append(f"forbidden identity token in tracked file: {rel}")
                break
    return errors


def scan_private_verboten_literals(root: Path, files: list[str]) -> list[str]:
    gmail_tokens = {t.casefold() for t in private_literal_values(root, "owner_gmail")}
    other_tokens = [
        token.casefold()
        for key in ("owner_name", "forbidden_attribution")
        for token in private_literal_values(root, key)
    ]
    tokens = list(gmail_tokens) + other_tokens
    if not tokens:
        return []
    # Narrow, mechanically-defined exception: AUTHORIZED_CONTRIBUTORS.md's whole
    # purpose is to list the real approved identity. Exempt ONLY a complete
    # line that exactly matches "cyre <owner_gmail>" (after stripping
    # surrounding whitespace) in that one file -- not a substring match
    # anywhere in the text, and only for the owner_gmail token specifically.
    # owner_name, forbidden_attribution, and any other occurrence of the
    # email (embedded in a longer line, appearing elsewhere in the file, or
    # anywhere in any other file) still block.
    errors: list[str] = []
    for rel in files:
        if rel in IDENTITY_DOC_EXCEPTIONS:
            continue
        path = root / rel
        if not path.is_file() or is_binary(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        is_allowlisted_file = rel == ".github/AUTHORIZED_CONTRIBUTORS.md"
        allowlisted_lines = (
            {line.strip().casefold() for line in text.splitlines()}
            if is_allowlisted_file
            else set()
        )
        text_lc = text.casefold()
        hit = False
        for token in tokens:
            if token not in text_lc:
                continue
            if (
                is_allowlisted_file
                and token in gmail_tokens
                and f"cyre <{token}>" in allowlisted_lines
            ):
                # Every occurrence of this exact gmail token in the file must
                # itself be confined to an exact allowlisted line -- check by
                # removing all exact-match lines and re-testing, rather than
                # a blanket substring replace.
                remaining_lc = "\n".join(
                    line
                    for line in text.splitlines()
                    if line.strip().casefold() != f"cyre <{token}>"
                ).casefold()
                if token not in remaining_lc:
                    continue
            hit = True
            break
        if hit:
            errors.append(f"private verboten literal in tracked file: {rel}")
    return errors


def scan_agent_private_surface(root: Path, files: list[str]) -> list[str]:
    """Apply the strict portable-brain boundary to every tracked .agent file.

    The local-only verboten registry remains the source of truth for exact
    private owner / forbidden-attribution literals. The .agent boundary is a
    stricter superset of the repo-wide guards because .agent is portable memory
    and protocol state: a superseded lesson row, rendered markdown view, or
    coordination note must not carry a private literal, personal path, local
    temp path, workspace topology, or secret pattern silently.

    Public bot/vendor domains and synthetic documentation domains are allowed
    for full email literals; personal mail domains are not. Error messages
    intentionally report only the path and line, never the literal value.
    """
    errors: list[str] = []
    private_tokens = [
        token.casefold()
        for key in ("owner_gmail", "owner_name", "forbidden_attribution")
        for token in private_literal_values(root, key)
    ]
    topology_tokens = [
        token.casefold()
        for token in local_topology_fragments(root)
        if token
    ]
    for rel in files:
        if not rel.startswith(".agent/"):
            continue
        path = root / rel
        if not path.is_file() or is_binary(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        # Graduated lesson candidates legitimately contain RFC 1918 private
        # IPs as operational evidence (e.g. DHCP drift, LAN peer addresses).
        # The exemption must follow the content through the whole memory
        # pipeline it flows through after graduation -- lessons.jsonl (the
        # accepted/superseded canonical store), its rendered LESSONS.md
        # view, and the episodic mirror -- not just the initial staging
        # file, or the same already-approved evidence gets flagged again
        # the moment it's accepted and rendered. Skip topology/RFC1918
        # scanning only for these files, only on lines that contain a
        # private IP literal. All other .agent guards remain active.
        operational_evidence_exempt = (
            rel
            in {
                ".agent/memory/semantic/lessons.jsonl",
                ".agent/memory/semantic/LESSONS.md",
                ".agent/memory/semantic/DECISIONS.md",
                ".agent/memory/episodic/AGENT_LEARNINGS.jsonl",
            }
            or (
                rel.startswith(".agent/memory/candidates/graduated/")
                and rel.endswith(".json")
            )
        )
        is_topology_exempt_file = rel in TOPOLOGY_TOKEN_EXCEPTIONS
        text_lc = text.casefold()
        if any(token and token in text_lc for token in private_tokens):
            errors.append(f"private verboten literal in .agent file: {rel}")
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            personal = PERSONAL_PATH_PATTERN.search(line)
            if personal:
                username = personal.group(1) or (
                    personal.group(2)
                    if personal.lastindex and personal.lastindex >= 2
                    else None
                )
                if username not in PERSONAL_PATH_PLACEHOLDERS:
                    errors.append(
                        f"personal absolute path in .agent file: {rel}:{line_no}"
                    )
                    break
            line_lc = line.casefold()
            has_private_ip = _RFC1918_PRIVATE_IP_RE.search(line)
            # RFC1918 IPs are unconditionally sensitive topology info,
            # independent of any configured secret -- graduated candidate
            # JSON is the one narrow, deliberate exemption (operational
            # network evidence). Every other .agent file still blocks them
            # outright, with no local-registry configuration required.
            if has_private_ip and not operational_evidence_exempt:
                errors.append(
                    f"private RFC1918 network topology in .agent file: {rel}:{line_no}"
                )
                break
            if not (operational_evidence_exempt and has_private_ip) and not is_topology_exempt_file:
                if any(token and token in line_lc for token in topology_tokens):
                    errors.append(
                        f"local/workspace path form in .agent file: {rel}:{line_no}"
                    )
                    break
            if not _line_has_secret_placeholder(line):
                for kind, pattern, _label in SECRET_PATTERNS:
                    if pattern.search(line):
                        errors.append(
                            f"secret pattern ({kind}) in .agent file: {rel}:{line_no}"
                        )
                        break
                else:
                    pass
                if errors and errors[-1].endswith(f"{rel}:{line_no}"):
                    break
            # The graduated-lesson RFC1918 exemption above covers IP
            # literals only. An email literal on the same line is a
            # DIFFERENT, independent leak and must still be caught --
            # deliberately NOT gated by operational_evidence_exempt/has_private_ip.
            for match in EMAIL_LITERAL_RE.finditer(line):
                email = match.group(0)
                domain = email.rsplit("@", 1)[1].casefold()
                if domain in AGENT_EMAIL_LITERAL_ALLOWED_DOMAINS:
                    continue
                errors.append(
                    f"private/unclassified email literal in .agent file: {rel}:{line_no}"
                )
                break
            else:
                continue
            break
    return errors


def scan_personal_paths(root: Path, files: list[str]) -> list[str]:
    """Block absolute /Users/<name>/ or /home/<name>/ paths in tracked files.

    Workstation paths in committed files are an OpSec leak (developer name,
    directory layout, sometimes machine hostname). They also break portability.
    Use ~, $REPO_ROOT, or <workspace> placeholders instead.
    """
    errors: list[str] = []
    for rel in files:
        if rel in PERSONAL_PATH_EXCEPTIONS:
            continue
        path = root / rel
        if not path.is_file() or is_binary(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            m = PERSONAL_PATH_PATTERN.search(line)
            if not m:
                continue
            # group(1) = Unix/Linux username; group(2) = Windows username
            username = m.group(1) or (m.group(2) if m.lastindex and m.lastindex >= 2 else None)
            if username and username in PERSONAL_PATH_PLACEHOLDERS:
                continue
            errors.append(
                f"personal absolute path in tracked file: {rel}:{line_no}: "
                f"matched {m.group(0)!r} — use $HOME/, %USERPROFILE%\\, or $REPO_ROOT"
            )
            break
    return errors


def scan_bidi_controls(root: Path, files: list[str]) -> list[str]:
    """Block Unicode BiDi control characters (Trojan-Source defense).

    These invisible characters can reorder source code so the rendered
    text differs from the parsed AST. CVE-2021-42574.
    """
    errors: list[str] = []
    for rel in files:
        if rel in BIDI_CONTROL_EXCEPTIONS:
            continue
        path = root / rel
        if not path.is_file() or is_binary(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for ch, name in BIDI_CONTROL_CHARS.items():
                if ch in line:
                    errors.append(
                        f"BiDi control char in tracked file: {rel}:{line_no}: "
                        f"U+{ord(ch):04X} ({name})"
                    )
                    break
            else:
                continue
            break
    return errors


def scan_mojibake(root: Path, files: list[str]) -> list[str]:
    """Block UTF-8 mojibake byte pairs in tracked text (LINT-007)."""
    errors: list[str] = []
    for rel in files:
        path = root / rel
        if not path.is_file() or is_binary(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            match = MOJIBAKE_RE.search(line)
            if match:
                errors.append(
                    f"UTF-8 mojibake in tracked file: {rel}:{line_no}: "
                    f"U+{ord(match.group()[0]):04X} mis-decoded sequence "
                    "(see docs/LESSONS.md 2026-06-10 / CIDF LINT-007)"
                )
                break
    return errors


def check_private_generated_tracking(files: list[str]) -> list[str]:
    return [
        f"private/generated config is tracked: {rel}"
        for rel in files
        if rel in PRIVATE_GENERATED_TRACKED
    ]


def check_generated_artifact_tracking(files: list[str]) -> list[str]:
    errors: list[str] = []
    for rel in files:
        if rel in GENERATED_ARTIFACT_EXCEPTIONS:
            continue
        if any(fnmatch.fnmatch(rel, pattern) for pattern in GENERATED_ARTIFACT_PATTERNS):
            errors.append(f"generated artifact is tracked: {rel}")
    return errors


def _line_has_secret_placeholder(line: str) -> bool:
    return any(marker in line for marker in SECRET_PLACEHOLDER_MARKERS)


def scan_tracked_secrets(root: Path, files: list[str]) -> list[str]:
    """Block committed API keys, bot tokens, private keys, and similar secrets."""
    errors: list[str] = []
    for rel in files:
        if rel in SECRET_PATTERN_EXCEPTIONS:
            continue
        path = root / rel
        if not path.is_file() or is_binary(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if _line_has_secret_placeholder(line):
                continue
            for kind, pattern, label in SECRET_PATTERNS:
                if pattern.search(line):
                    errors.append(
                        f"tracked secret pattern ({kind}): {rel}:{line_no} — {label}; "
                        "use ${env:VAR} placeholders or move to .env"
                    )
                    break
            else:
                continue
            break
    return errors


def check_git_internal_junk(root: Path) -> list[str]:
    git_dir = root / ".git"
    refs_dir = git_dir / "refs"
    if not refs_dir.exists():
        return []
    return [
        f"macOS metadata file inside git refs: {path.relative_to(root)}"
        for path in refs_dir.rglob(".DS_Store")
    ]


def check_identity(root: Path) -> list[str]:
    name = run_git(root, "config", "user.name").stdout.strip()
    email = run_git(root, "config", "user.email").stdout.strip()
    if os.getenv("GITHUB_ACTIONS") == "true" and not name and not email:
        return []
    identities = set(APPROVED_IDENTITIES)
    private_emails = {
        value.casefold() for value in private_literal_values(root, "owner_gmail")
    }
    private_names = [
        value.casefold() for value in private_literal_values(root, "owner_name")
    ]
    # Backward compatible: if no owner_name is configured, fall back to the
    # prior hardcoded "cyre" pairing rather than silently rejecting every
    # private-email identity for configs that never set owner_name.
    name_tokens = private_names or ["cyre"]
    private_identity_ok = (
        email.casefold() in private_emails
        and any(token in name.casefold() for token in name_tokens)
    )
    if (name, email) not in identities and not private_identity_ok:
        expected = " or ".join(f"{n} <{e}>" for n, e in sorted(APPROVED_IDENTITIES))
        return [
            "git identity mismatch: "
            f"found {name or '<unset>'} <{email or '<unset>'}>; "
            f"expected {expected}"
        ]
    return []


def _classify_prohibited_address(token: str) -> str | None:
    """Return rfc1918, loopback, ula, or cgnat when token is a prohibited literal."""
    try:
        addr = ipaddress.ip_address(token)
    except ValueError:
        return None
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if addr.is_loopback:
        return "loopback"
    if isinstance(addr, ipaddress.IPv4Address) and addr in _PROHIBITED_CGNAT_NET:
        return "cgnat"
    if any(addr in net for net in _PROHIBITED_RFC1918_NETS):
        return "rfc1918"
    if isinstance(addr, ipaddress.IPv6Address) and addr in _PROHIBITED_ULA_NET:
        return "ula"
    return None


def _parsed_address_token(raw: str) -> str | None:
    """Return a complete address literal, or None when the candidate is not one.

    Bracketed IPv6 drops the brackets and any trailing port. A bare token is
    parsed whole first, so a compressed address is not split on its last
    hextet. Only a token ipaddress rejects is retried with a trailing ``:port``
    removed (``192.168.0.1:8080``).
    """
    token = raw
    if token.startswith("[") and "]" in token:
        token = token[1:token.index("]")]
    try:
        ipaddress.ip_address(token)
    except ValueError:
        host, sep, port = token.rpartition(":")
        if not sep or not port.isdigit() or not host or host.endswith(":"):
            return None
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return None
        return host
    return token


def _prohibited_classes_in_text(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _STAGED_ADDRESS_TOKEN_RE.finditer(text):
        token = _parsed_address_token(match.group())
        if token is None:
            continue
        kind = _classify_prohibited_address(token)
        if kind and kind not in seen:
            seen.add(kind)
            found.append(kind)
    return found


def _apply_diff_file_header(raw: str) -> str | None:
    """Return the path from a ``+++`` header outside a hunk, or None for /dev/null."""
    path = raw[4:]
    if path == "/dev/null":
        return None
    if path.startswith(("b/", "a/")):
        path = path[2:]
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    return path


def _iter_staged_added_lines(diff_text: str):
    """Yield (path, new_line_no, line_text) for added lines in a cached diff.

    ``+++`` is a file header only before the first hunk. Inside a hunk an
    added line whose text starts with ``++`` is also ``+++...`` in the patch
    and must be scanned as content.
    """
    rel: str | None = None
    new_line: int | None = None
    in_hunk = False
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            rel = None
            new_line = None
            in_hunk = False
            continue
        if raw.startswith("@@"):
            in_hunk = True
            match = _HUNK_NEW_START_RE.search(raw)
            new_line = int(match.group(1)) if match else None
            continue
        if in_hunk:
            if rel is None or new_line is None:
                continue
            if raw.startswith("+"):
                yield rel, new_line, raw[1:]
                new_line += 1
            elif raw.startswith("-") or raw.startswith("\\"):
                continue
            else:
                new_line += 1
            continue
        if raw.startswith("+++ "):
            rel = _apply_diff_file_header(raw)


def _address_scan_diff_spec(
    diff_base: str | None,
    diff_head: str | None,
) -> tuple[list[str], str] | str:
    """Return ``(git diff args, finding location)`` or an error string.

    No endpoints means the index (``--cached``), which pre-commit uses.
    Both endpoints mean the three-dot range CI passes for a pull request.
    """
    if (diff_base is None) != (diff_head is None):
        return "diff base and head must both be set"
    if diff_base is None:
        return ["--cached"], "staged file"
    if (
        not diff_base
        or not diff_head
        or diff_base.startswith("-")
        or diff_head.startswith("-")
    ):
        return "diff refs must be non-empty and must not start with '-'"
    return [f"{diff_base}...{diff_head}"], "commit range"


def scan_staged_prohibited_address_literals(
    root: Path,
    *,
    diff_base: str | None = None,
    diff_head: str | None = None,
) -> list[str]:
    """Block prohibited address literals on added lines.

    Default is ``git diff --cached`` so pre-commit ignores unstaged overlay
    drift. CI passes ``diff_base`` and ``diff_head`` to scan the pull-request
    range, because a CI checkout has an empty index. Error text names the
    path, line, and address class, never the literal.
    """
    spec = _address_scan_diff_spec(diff_base, diff_head)
    if isinstance(spec, str):
        return [f"prohibited private-range scan failed: {spec}"]
    diff_args, where = spec
    proc = run_git(
        root,
        "diff",
        *diff_args,
        "-U0",
        "--no-color",
        "--diff-filter=ACMRT",
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or "git diff failed"
        return [f"prohibited private-range scan failed: {detail}"]
    errors: list[str] = []
    reported: set[tuple[str, int, str]] = set()
    for rel, line_no, line in _iter_staged_added_lines(proc.stdout):
        if rel in _PROHIBITED_ADDRESS_SCAN_EXCEPTIONS:
            continue
        for kind in _prohibited_classes_in_text(line):
            key = (rel, line_no, kind)
            if key in reported:
                continue
            reported.add(key)
            errors.append(
                f"prohibited private-range literal ({kind}) in {where}: {rel}:{line_no}"
            )
    return errors


def check_workflow_permissions(root: Path) -> list[str]:
    errors: list[str] = []
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists():
        return errors
    for path in sorted(workflow_dir.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        needs_write = any(marker in text for marker in WORKFLOW_WRITE_MARKERS)
        if not needs_write:
            continue
        rel = path.relative_to(root)
        if (
            "contents: write" not in text
            and "pull-requests: write" not in text
            and "issues: write" not in text
        ):
            errors.append(f"workflow may write but lacks explicit write permission: {rel}")
    return errors


def report_status(root: Path) -> list[str]:
    warnings: list[str] = []
    status = run_git(root, "status", "--short", "--branch")
    if status.returncode != 0:
        return [f"git status failed: {status.stderr.strip()}"]
    warnings.append(status.stdout.strip())
    shallow = run_git(root, "rev-parse", "--is-shallow-repository")
    if shallow.returncode == 0:
        warnings.append(f"shallow={shallow.stdout.strip()}")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Repo hygiene guard for Perpetua-Tools")
    parser.add_argument("repo", nargs="?", default=".", help="repository root")
    parser.add_argument(
        "--address-diff-base",
        default=None,
        help="base ref for the prohibited-address scan (CI); omit to scan the index",
    )
    parser.add_argument(
        "--address-diff-head",
        default=None,
        help="head ref for the prohibited-address scan (CI); required with --address-diff-base",
    )
    args = parser.parse_args()

    root = Path(args.repo).resolve()
    files = tracked_files(root)

    errors: list[str] = []
    errors.extend(check_identity(root))
    errors.extend(scan_forbidden_identity(root, files))
    errors.extend(scan_personal_paths(root, files))
    errors.extend(scan_bidi_controls(root, files))
    errors.extend(scan_mojibake(root, files))
    errors.extend(scan_tracked_secrets(root, files))
    errors.extend(check_private_generated_tracking(files))
    errors.extend(check_generated_artifact_tracking(files))
    errors.extend(check_git_internal_junk(root))
    errors.extend(check_workflow_permissions(root))
    errors.extend(scan_private_verboten_literals(root, files))
    errors.extend(scan_agent_private_surface(root, files))
    errors.extend(
        scan_staged_prohibited_address_literals(
            root,
            diff_base=args.address_diff_base,
            diff_head=args.address_diff_head,
        )
    )

    for line in report_status(root):
        print(f"INFO: {line}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("OK: repo hygiene checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
