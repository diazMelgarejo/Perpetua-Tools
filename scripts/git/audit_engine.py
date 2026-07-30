#!/usr/bin/env python3
"""audit_engine.py -- unified identity classification and audit engine.

Phases 1-2 of docs/plans/2026-07-24-unified-identity-audit-integrated-plan.md.
Single source of truth for approved Git author/committer identities,
consumed by repo_hygiene.py, check_identity.sh, and audit_attribution.sh.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

_POLICY_FILENAME = "identity-policy.json"
_SUPPORTED_VERSION = 1


class IdentityPolicyError(Exception):
    """Policy file missing, unreadable, malformed, or unsupported version."""


class AttributionCheckError(Exception):
    """The banned-attribution check itself failed to execute -- a missing
    library, a source failure, or an undefined helper function. Must never
    be treated as "no banned attribution found": that would make an
    execution failure fail open, indistinguishable from a genuine clean
    result."""


@dataclass(frozen=True)
class ClassificationResult:
    approved: bool
    reason: str
    matched_kind: str = ""


@dataclass(frozen=True)
class IdentityCheckResult:
    approved: bool
    exit_code: int
    messages: tuple[str, ...]


def _engine_dir() -> Path:
    return Path(__file__).resolve().parent


def openclaw_workspace_root(root: Path) -> Path:
    for candidate in (root, *root.parents):
        if (candidate / "orama-system").is_dir():
            return candidate
    return root


def private_literal_values(root: Path, key: str) -> list[str]:
    configured_path = os.getenv("OPENCLAW_VERBOTEN_LITERALS")
    path = Path(configured_path) if configured_path else openclaw_workspace_root(root) / ".verboten-literals.local"
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
        value = "".join(value.split())
        if value:
            values.append(value)
    return values


def _validate_policy_data(data: dict) -> None:
    # Container-type guards first, before any iteration -- valid JSON can
    # still have the wrong SHAPE (e.g. human_identities as an int,
    # repo_bot_identities as a list instead of a mapping). Without these
    # checks, iterating/`.items()`-ing the wrong type raises a bare
    # TypeError/AttributeError that escapes load_policy() uncaught,
    # bypassing the IdentityPolicyError fail-closed contract this module
    # exists to guarantee.
    if not isinstance(data["human_identities"], list):
        raise IdentityPolicyError("human_identities must be a list")
    if not isinstance(data["agent_identities"], list):
        raise IdentityPolicyError("agent_identities must be a list")
    if not isinstance(data["repo_bot_identities"], dict):
        raise IdentityPolicyError("repo_bot_identities must be an object")

    seen_emails: set[str] = set()

    def _track(email: str, label: str) -> None:
        if not isinstance(email, str) or not email:
            raise IdentityPolicyError(f"{label} must be a non-empty string")
        key = email.casefold()
        if key in seen_emails:
            raise IdentityPolicyError(f"duplicate identity email after normalization: {label}")
        seen_emails.add(key)

    for entry in data["human_identities"]:
        if not isinstance(entry, dict):
            raise IdentityPolicyError("human_identities entries must be objects")
        if "email" not in entry:
            raise IdentityPolicyError("human_identities entry missing required 'email' field")
        _track(entry["email"], entry["email"])
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            raise IdentityPolicyError(
                f"human_identities entry's 'aliases' must be a list, got {type(aliases).__name__}"
            )
        for alias in aliases:
            _track(alias, alias if isinstance(alias, str) else repr(alias))

    for entry in data["agent_identities"]:
        if not isinstance(entry, dict):
            raise IdentityPolicyError("agent_identities entries must be objects")
        if "email" not in entry:
            raise IdentityPolicyError("agent_identities entry missing required 'email' field")
        _track(entry["email"], entry["email"])

    for repo_name, bots in data["repo_bot_identities"].items():
        if not isinstance(bots, list):
            raise IdentityPolicyError(f"repo_bot_identities[{repo_name!r}] must be a list")
        for bot in bots:
            if not isinstance(bot, str) or not bot:
                raise IdentityPolicyError(
                    f"repo_bot_identities[{repo_name!r}] entries must be non-empty strings, "
                    f"got {bot!r}"
                )
            if "*" in bot:
                raise IdentityPolicyError(
                    f"universal bot wildcard patterns are not allowed: {bot!r} (repo {repo_name})"
                )
            _track(bot, bot)

    if "vendor_domains" in data:
        raise IdentityPolicyError("vendor_domains approval list is not permitted in identity policy")


def load_policy(policy_path: Optional[Path] = None) -> dict:
    path = policy_path or (_engine_dir() / _POLICY_FILENAME)
    if not path.is_file():
        raise IdentityPolicyError(f"identity policy file missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityPolicyError(f"identity policy file unreadable/invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise IdentityPolicyError("identity policy file must be a JSON object")
    version = data.get("version")
    if version != _SUPPORTED_VERSION:
        raise IdentityPolicyError(
            f"unsupported identity policy version {version!r}; "
            f"this engine only supports version {_SUPPORTED_VERSION}"
        )
    for required in ("human_identities", "agent_identities", "repo_bot_identities"):
        if required not in data:
            raise IdentityPolicyError(f"identity policy missing required key: {required}")
    _validate_policy_data(data)
    return data


def _env_approved_emails() -> set[str]:
    if os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("ORAMA_ALLOW_IDENTITY_ENV_OVERRIDE") != "1":
        return set()
    raw = os.getenv("ORAMA_APPROVED_EMAILS", "")
    if not raw.strip():
        return set()
    emails: set[str] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part or "@" not in part or "*" in part:
            raise IdentityPolicyError(f"invalid ORAMA_APPROVED_EMAILS entry: {part!r}")
        emails.add(part.casefold())
    return emails


def _private_identity_ok(
    name: str,
    email: str,
    root: Path,
    private_literal_values_fn: Callable[[Path, str], list[str]],
    *,
    email_only: bool,
) -> bool:
    private_emails = {v.casefold() for v in private_literal_values_fn(root, "owner_gmail")}
    if email.casefold() not in private_emails:
        return False
    if email_only:
        return True
    private_names = [v.casefold() for v in private_literal_values_fn(root, "owner_name")]
    name_tokens = private_names or ["cyre"]
    return any(token in name.casefold() for token in name_tokens)


_GITHUB_NUMERIC_BOT_PREFIX = re.compile(r"^\d+\+")


def _normalize_github_noreply_email(email: str) -> str:
    """Strip GitHub's numeric ID prefix from noreply bot addresses.

    Commits may use ``206951365+cursor[bot]@users.noreply.github.com`` while
    policy lists ``cursor[bot]@users.noreply.github.com``. Only normalizes
    ``@users.noreply.github.com`` addresses; does not broaden to other domains.
    """
    email_lc = email.strip().casefold()
    local, sep, domain = email_lc.partition("@")
    if sep != "@" or domain != "users.noreply.github.com":
        return email_lc
    return f"{_GITHUB_NUMERIC_BOT_PREFIX.sub('', local)}@{domain}"


def _repo_bot_approved(email: str, repo_bots: list[str]) -> bool:
    normalized = _normalize_github_noreply_email(email)
    return normalized in {_normalize_github_noreply_email(b) for b in repo_bots}


def is_approved_identity(
    name: str,
    email: str,
    *,
    root: Path,
    repo_name: str = "",
    policy_path: Optional[Path] = None,
    private_literal_values_fn: Optional[Callable[[Path, str], list[str]]] = None,
    profile: str = "strict",
) -> ClassificationResult:
    """Classify (name, email) against the unified policy (fail-closed on policy errors)."""
    policy = load_policy(policy_path)
    name_lc, email_lc = name.strip().casefold(), email.strip().casefold()
    literals_fn = private_literal_values_fn or private_literal_values

    if email_lc in _env_approved_emails():
        return ClassificationResult(True, "approved via ORAMA_APPROVED_EMAILS override", "env_override")

    if profile == "configured":
        for entry in policy["human_identities"]:
            if email_lc == entry["email"].casefold():
                return ClassificationResult(True, "approved human identity", "human")
            for alias in entry.get("aliases", []):
                if email_lc == alias.casefold():
                    return ClassificationResult(True, "approved human identity (alias)", "human_alias")
        for entry in policy["agent_identities"]:
            if entry["email"].casefold() == email_lc:
                allowed = [n.casefold() for n in entry.get("allowed_names", [])]
                if not allowed or name_lc in allowed:
                    return ClassificationResult(True, "approved agent identity", "agent")
                return ClassificationResult(
                    False,
                    f"email {email!r} is an approved agent identity, but name {name!r} "
                    f"is not in its allowed_names",
                )
        if _private_identity_ok(name, email, root, literals_fn, email_only=True):
            return ClassificationResult(True, "approved private owner identity", "private")
        return ClassificationResult(False, f"identity {name!r} <{email!r}> not found in policy")

    if profile == "audit_relaxed":
        if email_lc == "cursoragent@cursor.com" or ("cursor" in name_lc and "agent" in name_lc):
            return ClassificationResult(True, "approved Cursor Agent identity", "agent")
        for entry in policy["human_identities"]:
            if email_lc == entry["email"].casefold():
                return ClassificationResult(True, "approved human identity", "human")
            for alias in entry.get("aliases", []):
                if email_lc == alias.casefold():
                    return ClassificationResult(True, "approved human identity (alias)", "human_alias")
        for entry in policy["agent_identities"]:
            if entry["email"].casefold() == email_lc:
                return ClassificationResult(True, "approved agent identity", "agent")
        repo_bots = policy["repo_bot_identities"].get(repo_name, [])
        if _repo_bot_approved(email, repo_bots):
            return ClassificationResult(True, f"approved bot identity for {repo_name}", "repo_bot")
        if _private_identity_ok(name, email, root, literals_fn, email_only=True):
            return ClassificationResult(True, "approved private owner identity", "private")
        return ClassificationResult(False, f"identity {name!r} <{email!r}> not found in policy")

    for entry in policy["human_identities"]:
        if entry["email"].casefold() == email_lc and entry["name"].casefold() == name_lc:
            return ClassificationResult(True, "approved human identity", "human")
        for alias in entry.get("aliases", []):
            if alias.casefold() == email_lc and entry["name"].casefold() == name_lc:
                return ClassificationResult(True, "approved human identity (alias)", "human_alias")

    for entry in policy["agent_identities"]:
        if entry["email"].casefold() == email_lc:
            allowed = [n.casefold() for n in entry.get("allowed_names", [])]
            if not allowed or name_lc in allowed:
                return ClassificationResult(True, "approved agent identity", "agent")
            return ClassificationResult(
                False,
                f"email {email!r} is an approved agent identity, but name {name!r} "
                f"is not in its allowed_names {entry.get('allowed_names', [])!r}",
            )

    repo_bots = policy["repo_bot_identities"].get(repo_name, [])
    if _repo_bot_approved(email, repo_bots):
        return ClassificationResult(True, f"approved bot identity for {repo_name}", "repo_bot")

    if _private_identity_ok(name, email, root, literals_fn, email_only=False):
        return ClassificationResult(True, "approved private owner identity", "private")

    return ClassificationResult(False, f"identity {name!r} <{email!r}> not found in policy")


def is_cursor_agent_context(name: str, email: str) -> bool:
    for var in ("CURSOR_AGENT", "CURSOR_TRACE_ID", "CURSOR_SESSION_ID"):
        if os.getenv(var):
            return True
    name_lc = name.casefold()
    email_lc = email.casefold()
    if "cursor" in name_lc:
        return True
    return email_lc.endswith("@cursor.com") or email_lc.endswith("@cursor.sh")


def check_configured_identity(
    repo_root: Path,
    *,
    cursor_scoped: bool = True,
    policy_path: Optional[Path] = None,
    private_literal_values_fn: Optional[Callable[[Path, str], list[str]]] = None,
) -> IdentityCheckResult:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.name"],
        capture_output=True,
        text=True,
        check=False,
    )
    name = (proc.stdout or "").strip()
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.email"],
        capture_output=True,
        text=True,
        check=False,
    )
    email = (proc.stdout or "").strip()
    lines = (
        f"git user.name={name or '<unset>'}",
        f"git user.email={email or '<unset>'}",
    )

    if cursor_scoped and not is_cursor_agent_context(name, email):
        return IdentityCheckResult(True, 0, lines)

    if not name or not email:
        return IdentityCheckResult(
            False,
            1,
            lines + ("ERROR: set user.name and user.email before committing",),
        )

    try:
        result = is_approved_identity(
            name,
            email,
            root=repo_root,
            repo_name=repo_root.name,
            policy_path=policy_path,
            private_literal_values_fn=private_literal_values_fn,
            profile="configured",
        )
    except IdentityPolicyError as exc:
        return IdentityCheckResult(False, 1, lines + (f"ERROR: {exc}",))

    if result.approved:
        return IdentityCheckResult(True, 0, lines + ("OK: approved git identity",))

    error_lines = (
        "ERROR: git identity must match scripts/git/identity-policy.json "
        "(human, agent, private owner, or approved alias).",
        f"  found: {name} <{email}>",
        f"  reason: {result.reason}",
    )
    return IdentityCheckResult(False, 1, lines + error_lines)


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _bash_banned_attribution_hit(
    repo_root: Path,
    ae_lc: str,
    an_lc: str,
    ce_lc: str,
    cn_lc: str,
    body_lc: str,
) -> bool:
    lib = _engine_dir() / "banned_attribution_lib.sh"
    # lib and repo_root passed as positional args ($6/$7), same as the
    # other 5 values -- never interpolated into the script text itself.
    # An f-string-interpolated path containing a shell metacharacter
    # (unlikely in practice, but not something to rely on) would
    # otherwise be a real injection point.
    script = (
        'set -u\n'
        'source "$6" || exit 2\n'
        'declare -f banned_attribution_hit >/dev/null 2>&1 || exit 2\n'
        'root="$7"\n'
        'if banned_attribution_hit "$1" "$2" "$3" "$4" "$5" "$root"; then exit 0; else exit 1; fi'
    )
    proc = subprocess.run(
        [
            "bash", "-c", script, "banned_attribution_hit",
            ae_lc, an_lc, ce_lc, cn_lc, body_lc, str(lib), str(repo_root),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    # 0 = hit, 1 = no hit -- both legitimate results of the check actually
    # running. Any other code (2 = source/helper-definition failure
    # explicitly, anything else = an unexpected internal error) must NOT
    # be silently treated as "no hit": that would make a missing library
    # or a broken helper function indistinguishable from a clean pass,
    # exactly the fail-open behavior audit_engine.py exists to prevent.
    if proc.returncode not in (0, 1):
        raise AttributionCheckError(
            f"banned_attribution_hit execution failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip() or 'no output'}"
        )
    return proc.returncode == 0


def _coauthor_policy_ok(repo_root: Path, body: str) -> bool:
    hook = repo_root / "scripts/git/check_commit_message.sh"
    if not hook.is_file() or not os.access(hook, os.X_OK):
        return True
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
        tmp.write(body)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            [str(hook), tmp_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode == 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _preferred_bot_label(repo_root: Path, policy: dict) -> str:
    bots = policy.get("repo_bot_identities", {}).get(repo_root.name, [])
    if not bots:
        return "any"
    return bots[0]


def _audit_ref(
    repo_root: Path,
    ref: str,
    history_count: int,
    policy_path: Optional[Path],
    private_literal_values_fn: Optional[Callable[[Path, str], list[str]]],
) -> str:
    sha_proc = _run_git(repo_root, "rev-parse", "-q", "--verify", ref)
    if sha_proc.returncode != 0:
        return f"{ref}\tMISSING\t-\t-\t-\t-\n"
    sha = (sha_proc.stdout or "").strip()
    policy = load_policy(policy_path)
    preferred_bot = _preferred_bot_label(repo_root, policy)
    banned = bad_author = bad_co = count = 0
    log_proc = _run_git(repo_root, "log", f"-{history_count}", "--format=%H", ref)
    for commit_hash in (log_proc.stdout or "").splitlines():
        commit_hash = commit_hash.strip()
        if not commit_hash:
            continue
        count += 1
        body = (_run_git(repo_root, "log", "-1", "--format=%B", commit_hash).stdout or "")
        ae = (_run_git(repo_root, "log", "-1", "--format=%ae", commit_hash).stdout or "").strip()
        an = (_run_git(repo_root, "log", "-1", "--format=%an", commit_hash).stdout or "").strip()
        ae_lc, an_lc = ae.casefold(), an.casefold()
        ce = (_run_git(repo_root, "log", "-1", "--format=%ce", commit_hash).stdout or "").strip()
        cn = (_run_git(repo_root, "log", "-1", "--format=%cn", commit_hash).stdout or "").strip()
        ce_lc, cn_lc = ce.casefold(), cn.casefold()
        body_lc = body.casefold()
        if _bash_banned_attribution_hit(repo_root, ae_lc, an_lc, ce_lc, cn_lc, body_lc):
            banned += 1
        author = is_approved_identity(
            an,
            ae,
            root=repo_root,
            repo_name=repo_root.name,
            policy_path=policy_path,
            private_literal_values_fn=private_literal_values_fn,
            profile="audit_relaxed",
        )
        if not author.approved:
            bad_author += 1
        if not _coauthor_policy_ok(repo_root, body):
            bad_co += 1
    clean = "yes" if banned == 0 and bad_author == 0 and bad_co == 0 else "no"
    return (
        f"{ref}\t{sha[:12]}\tbanned={banned}\tbad_author={bad_author}\t"
        f"bad_coauthor={bad_co}\tcommits={count}\tclean={clean}\trepo_bot={preferred_bot}\n"
    )


def run_attribution_audit(
    repo_root: Path,
    *,
    history_count: int = 79,
    audit_range: str = "",
    strict: bool = False,
    policy_path: Optional[Path] = None,
    private_literal_values_fn: Optional[Callable[[Path, str], list[str]]] = None,
) -> int:
    repo_root = repo_root.resolve()
    os.chdir(repo_root)
    range_spec = audit_range or os.getenv("GIT_AUDIT_RANGE", "")
    include_context = (
        not range_spec
        or os.getenv("GIT_AUDIT_INCLUDE_CONTEXT_REFS", "0") == "1"
    )
    lines: list[str] = []
    if include_context:
        for ref in ("HEAD", "main", "origin/main"):
            lines.append(
                _audit_ref(
                    repo_root,
                    ref,
                    history_count,
                    policy_path,
                    private_literal_values_fn,
                )
            )
        sys.stdout.write("".join(lines))

    if not range_spec:
        return 0

    range_banned = range_bad_author = range_bad_co = range_count = 0
    rev_proc = _run_git(repo_root, "rev-list", range_spec)
    for commit_hash in (rev_proc.stdout or "").splitlines():
        commit_hash = commit_hash.strip()
        if not commit_hash:
            continue
        range_count += 1
        body = (_run_git(repo_root, "log", "-1", "--format=%B", commit_hash).stdout or "")
        ae = (_run_git(repo_root, "log", "-1", "--format=%ae", commit_hash).stdout or "").strip()
        an = (_run_git(repo_root, "log", "-1", "--format=%an", commit_hash).stdout or "").strip()
        ae_lc, an_lc = ae.casefold(), an.casefold()
        ce = (_run_git(repo_root, "log", "-1", "--format=%ce", commit_hash).stdout or "").strip()
        cn = (_run_git(repo_root, "log", "-1", "--format=%cn", commit_hash).stdout or "").strip()
        ce_lc, cn_lc = ce.casefold(), cn.casefold()
        body_lc = body.casefold()
        oneline = (_run_git(repo_root, "log", "-1", "--oneline", commit_hash).stdout or "").strip()
        if _bash_banned_attribution_hit(repo_root, ae_lc, an_lc, ce_lc, cn_lc, body_lc):
            range_banned += 1
            print(f"banned_attribution: {commit_hash} {oneline}", file=sys.stderr)
        author = is_approved_identity(
            an,
            ae,
            root=repo_root,
            repo_name=repo_root.name,
            policy_path=policy_path,
            private_literal_values_fn=private_literal_values_fn,
            profile="audit_relaxed",
        )
        if not author.approved:
            range_bad_author += 1
            print(f"bad_author: {commit_hash} {an} <{ae}>", file=sys.stderr)
        if not _coauthor_policy_ok(repo_root, body):
            range_bad_co += 1
            print(f"bad_coauthor: {commit_hash} {oneline}", file=sys.stderr)

    range_clean = "yes" if range_banned == 0 and range_bad_author == 0 and range_bad_co == 0 else "no"
    sys.stdout.write(
        f"RANGE\t{range_spec}\tbanned={range_banned}\tbad_author={range_bad_author}\t"
        f"bad_coauthor={range_bad_co}\tcommits={range_count}\tclean={range_clean}\n"
    )
    strict_flag = strict or os.getenv("GIT_AUDIT_STRICT") == "1"
    if strict_flag and range_clean != "yes":
        return 1
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Unified git identity policy engine")
    sub = parser.add_subparsers(dest="command", required=True)

    cfg = sub.add_parser("configured-identity", help="Check git config user identity")
    cfg.add_argument("--repo", type=Path, required=True)
    cfg.add_argument("--cursor-scoped", action="store_true", default=False)

    audit = sub.add_parser("audit", help="Audit commit attribution")
    audit.add_argument("--repo", type=Path, required=True)
    audit.add_argument("--history-count", type=int, default=79)
    audit.add_argument("--range", default="")
    audit.add_argument("--strict", action="store_true", default=False)

    args = parser.parse_args(argv)
    if args.command == "configured-identity":
        result = check_configured_identity(args.repo, cursor_scoped=args.cursor_scoped)
        for line in result.messages:
            stream = sys.stderr if line.startswith("ERROR:") else sys.stdout
            print(line, file=stream)
        return result.exit_code
    if args.command == "audit":
        return run_attribution_audit(
            args.repo,
            history_count=args.history_count,
            audit_range=args.range,
            strict=args.strict,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
