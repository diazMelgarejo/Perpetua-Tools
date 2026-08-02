#!/usr/bin/env python3
"""HMAC-bound operator grant for append-pr-body.sh (grant v2).

Same-user Keychain HMAC is escalation control, not cryptographic human identity.
A process running as the operator user (including agent shells with PTY) can read the
Keychain item or ack file; MVP raises effort, not proves human presence.
WebAuthn / MCP approval is deferred to security-sentinel v2.1.

Canonical HMAC payload (UTF-8 bytes, fixed field order, pipe-delimited, no trailing newline):

    grant-v2|{repo}|{pr_number}|{nonce}|{issued_at}|{action}|{content_digest}

--file digest: sha256 of raw file bytes. --message digest: sha256 of exact UTF-8 string
(no NFC/NFKC normalization, no newline trimming).

Replay state machine (nonce ledger in NONCE_STATE_PATH):

    minted -> reserved (append starts) -> remote_applied (gh edit OK) -> consumed

Crash after remote_applied: re-run append with same grant; reserve idempotent, reconcile
to consume without duplicate edit when body already contains the follow-up block.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GRANT_MARKER = "operator-grant-v2"
GRANT_TTL_SECONDS = 8 * 3600
DEFAULT_ACTION = "append_integrative"
ACK_PATH = Path.home() / ".cursor" / "pr-body-human-override-ack"
NONCE_STATE_PATH = Path.home() / ".cursor" / "pr-body-grant-nonces.json"
SECRET_SERVICE = "openclaw.pr_body_grant.hmac"
SECRET_ACCOUNT = "openclaw"
FALLBACK_SECRET_PATH = Path.home() / ".openclaw" / "secrets" / "pr_body_grant_hmac"
ENV_SECRET = "PR_BODY_GRANT_HMAC_SECRET"


class GrantError(Exception):
    """Actionable grant failure for operators."""


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def canonical_payload_bytes(
    repo: str,
    pr_number: str,
    nonce: str,
    issued_at: str,
    action: str,
    content_digest: str,
) -> bytes:
    """Fixed-order UTF-8 payload bytes used for HMAC mint and verify."""
    payload = (
        f"grant-v2|{repo}|{pr_number}|{nonce}|{issued_at}|{action}|{content_digest}"
    )
    return payload.encode("utf-8")


def _canonical_payload(
    repo: str,
    pr_number: str,
    nonce: str,
    issued_at: str,
    action: str,
    content_digest: str,
) -> bytes:
    return canonical_payload_bytes(
        repo, pr_number, nonce, issued_at, action, content_digest
    )


def content_digest_for_append(
    file_path: str | None,
    message: str | None,
    cwd: Path | None = None,
) -> str:
    if file_path:
        path = Path(file_path)
        if not path.is_absolute():
            base = cwd or Path.cwd()
            path = base / path
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise GrantError(f"cannot read append file for digest: {path}: {exc}") from exc
    elif message is not None:
        data = message.encode("utf-8")
    else:
        raise GrantError("provide --file or --message for content digest")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _read_secret_from_keychain() -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        proc = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                SECRET_SERVICE,
                "-a",
                SECRET_ACCOUNT,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except OSError:
        return None
    return None


def _ensure_keychain_secret() -> str:
    existing = _read_secret_from_keychain()
    if existing:
        return existing
    new_secret = secrets.token_hex(32)
    proc = subprocess.run(
        [
            "/usr/bin/security",
            "add-generic-password",
            "-U",
            "-s",
            SECRET_SERVICE,
            "-a",
            SECRET_ACCOUNT,
            "-w",
            new_secret,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GrantError(
            "failed to create Keychain secret "
            f"({SECRET_SERVICE}): {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return new_secret


def _read_fallback_secret_file() -> str | None:
    if not FALLBACK_SECRET_PATH.is_file():
        return None
    try:
        return FALLBACK_SECRET_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _validate_repo_slug(repo: str) -> None:
    if "|" in repo or not repo.strip():
        raise GrantError("grant repo must not contain pipe characters")


def _write_private_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)


def _write_fallback_secret_file(secret: str) -> None:
    _write_private_file(FALLBACK_SECRET_PATH, secret + "\n")


def resolve_hmac_secret(allow_generate: bool = False) -> bytes:
    env_val = os.environ.get(ENV_SECRET)
    if env_val:
        return env_val.encode("utf-8")

    keychain = _read_secret_from_keychain()
    if keychain:
        return keychain.encode("utf-8")

    file_val = _read_fallback_secret_file()
    if file_val:
        return file_val.encode("utf-8")

    if not allow_generate:
        raise GrantError(
            "HMAC secret missing. On macOS run grant from an operator terminal "
            f"(creates Keychain item {SECRET_SERVICE}). "
            f"Else create {FALLBACK_SECRET_PATH} (mode 0600) or set {ENV_SECRET} for tests."
        )

    if sys.platform == "darwin":
        secret = _ensure_keychain_secret()
    else:
        secret = secrets.token_hex(32)
        _write_fallback_secret_file(secret)
    return secret.encode("utf-8")


def _sign(secret: bytes, payload: bytes) -> str:
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _constant_time_eq(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


def parse_ack_text(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
        elif line in (GRANT_MARKER, "operator-grant-v1"):
            fields["marker"] = line
    return fields


def read_ack_fields() -> dict[str, str]:
    if not ACK_PATH.is_file():
        return {}
    try:
        return parse_ack_text(ACK_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _grant_ttl_ok(issued_raw: str) -> bool:
    issued = _parse_timestamp(issued_raw)
    if issued is None:
        return False
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    age = (_now_utc() - issued.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= GRANT_TTL_SECONDS


@contextmanager
def _locked_nonce_state():
    NONCE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = open(NONCE_STATE_PATH, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        raw = handle.read()
        if raw.strip():
            try:
                state = json.loads(raw)
            except json.JSONDecodeError:
                state = {"nonces": {}}
        else:
            state = {"nonces": {}}
        if "nonces" not in state or not isinstance(state["nonces"], dict):
            state["nonces"] = {}
        if "reservations" not in state or not isinstance(state.get("reservations"), dict):
            state["reservations"] = {}
        yield handle, state
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _write_nonce_state(handle: Any, state: dict[str, Any]) -> None:
    handle.seek(0)
    handle.truncate()
    json.dump(state, handle)
    handle.flush()
    os.fsync(handle.fileno())


def _prune_nonce_state(state: dict[str, Any]) -> None:
    nonces = state.get("nonces", {})
    reservations = state.get("reservations", {})
    cutoff = _now_utc().timestamp() - GRANT_TTL_SECONDS
    for nonce, ts in list(nonces.items()):
        parsed = _parse_timestamp(str(ts))
        if parsed is None:
            del nonces[nonce]
            continue
        if parsed.timestamp() < cutoff:
            del nonces[nonce]
    for nonce, entry in list(reservations.items()):
        at_raw = entry.get("at", "") if isinstance(entry, dict) else ""
        parsed = _parse_timestamp(str(at_raw))
        if parsed is None or parsed.timestamp() < cutoff:
            del reservations[nonce]
    state["nonces"] = nonces
    state["reservations"] = reservations


def _reservation_matches(
    entry: dict[str, Any],
    repo: str,
    pr_number: str,
    content_digest: str,
) -> bool:
    return (
        entry.get("repo", "") == repo
        and entry.get("pr", "") == str(pr_number)
        and entry.get("digest", "") == content_digest
    )


def _reservation_blocks_verify(
    nonce: str,
    repo: str,
    pr_number: str,
    content_digest: str,
) -> tuple[bool, str]:
    with _locked_nonce_state() as (_handle, state):
        _prune_nonce_state(state)
        entry = state.get("reservations", {}).get(nonce)
        if not entry:
            return True, ""
        if _reservation_matches(entry, repo, pr_number, content_digest):
            return True, ""
        return False, "grant nonce reserved for a different append operation"


def reserve_nonce_atomic(
    nonce: str,
    repo: str,
    pr_number: str,
    content_digest: str,
) -> tuple[bool, str]:
    """Reserve nonce before remote mutation. Idempotent for the same binding."""
    with _locked_nonce_state() as (handle, state):
        _prune_nonce_state(state)
        if nonce in state["nonces"]:
            return False, "grant nonce already consumed (replay blocked)"
        reservations = state["reservations"]
        existing = reservations.get(nonce)
        if existing:
            if _reservation_matches(existing, repo, pr_number, content_digest):
                return True, ""
            return False, "grant nonce reserved for a different append operation"
        reservations[nonce] = {
            "at": _now_utc().isoformat().replace("+00:00", "Z"),
            "repo": repo,
            "pr": str(pr_number),
            "digest": content_digest,
            "remote_applied": False,
        }
        _write_nonce_state(handle, state)
        return True, ""


def mark_remote_applied_atomic(nonce: str) -> tuple[bool, str]:
    """Mark remote PR body mutation successful; required before consume."""
    with _locked_nonce_state() as (handle, state):
        _prune_nonce_state(state)
        reservations = state["reservations"]
        entry = reservations.get(nonce)
        if not entry:
            return False, "grant nonce not reserved"
        entry["remote_applied"] = True
        _write_nonce_state(handle, state)
        return True, ""


def release_nonce_reservation_atomic(nonce: str) -> None:
    """Drop an in-flight reservation when remote mutation did not succeed."""
    with _locked_nonce_state() as (handle, state):
        _prune_nonce_state(state)
        entry = state.get("reservations", {}).get(nonce)
        if entry and not entry.get("remote_applied"):
            del state["reservations"][nonce]
            _write_nonce_state(handle, state)


def nonce_is_consumed(nonce: str) -> bool:
    with _locked_nonce_state() as (_handle, state):
        _prune_nonce_state(state)
        return nonce in state["nonces"]


def consume_nonce_atomic(nonce: str, require_remote_applied: bool = True) -> bool:
    """Mark nonce consumed once after remote success. Returns False if invalid."""
    with _locked_nonce_state() as (handle, state):
        _prune_nonce_state(state)
        if nonce in state["nonces"]:
            return False
        entry = state.get("reservations", {}).get(nonce)
        if require_remote_applied:
            if not entry or not entry.get("remote_applied"):
                return False
        state["nonces"][nonce] = _now_utc().isoformat().replace("+00:00", "Z")
        if nonce in state.get("reservations", {}):
            del state["reservations"][nonce]
        _write_nonce_state(handle, state)
        return True


def verify_grant_fields(
    fields: dict[str, str],
    repo: str,
    pr_number: str,
    content_digest: str,
    action: str = DEFAULT_ACTION,
    check_nonce_consumed: bool = True,
) -> tuple[bool, str]:
    try:
        _validate_repo_slug(repo)
    except GrantError as exc:
        return False, str(exc)

    if fields.get("marker") != GRANT_MARKER:
        if fields.get("marker") == "operator-grant-v1":
            return False, (
                "operator-grant-v1 is no longer accepted; re-run grant with matching "
                "--file or --message in an operator terminal"
            )
        return False, "operator grant file missing or not grant v2"

    issued = fields.get("issued-at", "")
    if not _grant_ttl_ok(issued):
        return False, "operator grant expired or invalid issued-at (8h TTL)"

    if fields.get("repo", "") != repo:
        return False, f"grant repo mismatch (grant={fields.get('repo')} want={repo})"

    if fields.get("pr-number", "") != str(pr_number):
        return False, (
            f"grant PR mismatch (grant={fields.get('pr-number')} want={pr_number})"
        )

    grant_action = fields.get("action", DEFAULT_ACTION)
    if grant_action != action:
        return False, f"grant action mismatch (grant={grant_action} want={action})"

    grant_digest = fields.get("content-digest", "")
    if grant_digest != content_digest:
        return False, "grant content-digest mismatch; re-grant with the same append payload"

    nonce = fields.get("grant-nonce", "")
    if not nonce:
        return False, "grant missing grant-nonce"

    if check_nonce_consumed and nonce_is_consumed(nonce):
        return False, "grant nonce already consumed (replay blocked)"

    ok_res, res_err = _reservation_blocks_verify(nonce, repo, pr_number, content_digest)
    if not ok_res:
        return False, res_err

    token = fields.get("token", "")
    if not token:
        return False, "grant missing HMAC token"

    try:
        secret = resolve_hmac_secret(allow_generate=False)
    except GrantError as exc:
        return False, str(exc)

    payload = _canonical_payload(
        repo,
        str(pr_number),
        nonce,
        issued,
        grant_action,
        grant_digest,
    )
    expected = _sign(secret, payload)
    if not _constant_time_eq(token, expected):
        return False, "grant HMAC verification failed"

    return True, ""


def verify_grant_for_append(
    repo: str,
    pr_number: str,
    file_path: str | None,
    message: str | None,
    consume: bool = False,
    cwd: Path | None = None,
) -> tuple[bool, str]:
    try:
        digest = content_digest_for_append(file_path, message, cwd=cwd)
    except GrantError as exc:
        return False, str(exc)

    fields = read_ack_fields()
    ok, err = verify_grant_fields(
        fields,
        repo,
        str(pr_number),
        digest,
        action=DEFAULT_ACTION,
        check_nonce_consumed=True,
    )
    if not ok:
        return False, err

    if consume:
        nonce = fields.get("grant-nonce", "")
        if not consume_nonce_atomic(nonce, require_remote_applied=True):
            return False, (
                "grant consume blocked: remote mutation not marked successful "
                "(replay or crash state — re-run append-pr-body.sh)"
            )
        try:
            ACK_PATH.unlink(missing_ok=True)
        except OSError as exc:
            return False, f"failed to remove consumed grant file: {exc}"

    return True, ""


def reserve_grant_for_append(
    repo: str,
    pr_number: str,
    file_path: str | None,
    message: str | None,
    cwd: Path | None = None,
) -> tuple[bool, str]:
    try:
        digest = content_digest_for_append(file_path, message, cwd=cwd)
    except GrantError as exc:
        return False, str(exc)
    fields = read_ack_fields()
    ok, err = verify_grant_fields(
        fields,
        repo,
        str(pr_number),
        digest,
        action=DEFAULT_ACTION,
        check_nonce_consumed=True,
    )
    if not ok:
        return False, err
    nonce = fields.get("grant-nonce", "")
    return reserve_nonce_atomic(nonce, repo, str(pr_number), digest)


def mark_remote_applied_for_append(
    repo: str,
    pr_number: str,
    file_path: str | None,
    message: str | None,
    cwd: Path | None = None,
) -> tuple[bool, str]:
    try:
        digest = content_digest_for_append(file_path, message, cwd=cwd)
    except GrantError as exc:
        return False, str(exc)
    fields = read_ack_fields()
    nonce = fields.get("grant-nonce", "")
    if not nonce:
        return False, "grant missing grant-nonce"
    entry_ok, entry_err = _reservation_blocks_verify(
        nonce, repo, str(pr_number), digest
    )
    if not entry_ok:
        return False, entry_err
    return mark_remote_applied_atomic(nonce)


def release_grant_for_append(
    repo: str,
    pr_number: str,
    file_path: str | None,
    message: str | None,
    cwd: Path | None = None,
) -> tuple[bool, str]:
    try:
        digest = content_digest_for_append(file_path, message, cwd=cwd)
    except GrantError as exc:
        return False, str(exc)
    fields = read_ack_fields()
    nonce = fields.get("grant-nonce", "")
    if not nonce:
        return False, "grant missing grant-nonce"
    entry = None
    with _locked_nonce_state() as (_handle, state):
        _prune_nonce_state(state)
        entry = state.get("reservations", {}).get(nonce)
    if entry and not _reservation_matches(entry, repo, str(pr_number), digest):
        return False, "grant nonce reserved for a different append operation"
    release_nonce_reservation_atomic(nonce)
    return True, ""


def follow_up_already_present(remote_body: str, append_block: str, title: str) -> bool:
    """Crash reconciliation: remote body already contains this follow-up block."""
    needle = f"## {title}\n\n{append_block}"
    return needle in remote_body


def reconcile_pending_consume(
    repo: str,
    pr_number: str,
    file_path: str | None,
    message: str | None,
    remote_body: str,
    title: str,
    cwd: Path | None = None,
) -> tuple[bool, str]:
    """Consume grant when remote already has the follow-up (post-crash recovery)."""
    try:
        digest = content_digest_for_append(file_path, message, cwd=cwd)
    except GrantError as exc:
        return False, str(exc)
    if message is not None:
        append_block = message
    elif file_path:
        try:
            path = Path(file_path)
            if not path.is_absolute():
                base = cwd or Path.cwd()
                path = base / path
            append_block = path.read_text(encoding="utf-8")
        except OSError as exc:
            return False, f"cannot read append file for reconcile: {exc}"
    else:
        return False, "provide --file or --message for reconcile"
    if not follow_up_already_present(remote_body, append_block, title):
        return False, "remote body missing expected follow-up block"
    fields = read_ack_fields()
    ok, err = verify_grant_fields(
        fields,
        repo,
        str(pr_number),
        digest,
        action=DEFAULT_ACTION,
        check_nonce_consumed=True,
    )
    if not ok:
        return False, err
    nonce = fields.get("grant-nonce", "")
    reserve_ok, reserve_err = reserve_nonce_atomic(nonce, repo, str(pr_number), digest)
    if not reserve_ok:
        return False, reserve_err
    mark_ok, mark_err = mark_remote_applied_atomic(nonce)
    if not mark_ok:
        return False, mark_err
    return verify_grant_for_append(
        repo,
        pr_number,
        file_path,
        message,
        consume=True,
        cwd=cwd,
    )


def mint_grant(
    repo: str,
    pr_number: str,
    file_path: str | None,
    message: str | None,
    cwd: Path | None = None,
) -> Path:
    _validate_repo_slug(repo)
    digest = content_digest_for_append(file_path, message, cwd=cwd)
    secret = resolve_hmac_secret(allow_generate=True)
    issued_at = _now_utc().isoformat().replace("+00:00", "Z")
    nonce = secrets.token_urlsafe(24)
    payload = _canonical_payload(
        repo,
        str(pr_number),
        nonce,
        issued_at,
        DEFAULT_ACTION,
        digest,
    )
    token = _sign(secret, payload)

    ACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = (
        f"{GRANT_MARKER}\n"
        f"issued-at={issued_at}\n"
        f"repo={repo}\n"
        f"pr-number={pr_number}\n"
        f"action={DEFAULT_ACTION}\n"
        f"content-digest={digest}\n"
        f"grant-nonce={nonce}\n"
        f"token={token}\n"
    )
    _write_private_file(ACK_PATH, body)
    return ACK_PATH


APPEND_SEGMENT_RE = re.compile(
    r"append-pr-body\.sh\s+([^\s]+)\s+(\d+)(?:\s+(.*))?$"
)


def parse_append_segment(segment: str) -> tuple[str, str, str | None, str | None] | None:
    seg = segment.strip()
    if "append-pr-body.sh" not in seg:
        return None
    match = APPEND_SEGMENT_RE.search(seg)
    if not match:
        return None
    repo = match.group(1)
    pr = match.group(2)
    rest = (match.group(3) or "").strip()
    file_path: str | None = None
    message: str | None = None
    tokens = rest.split()
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token == "--file" and idx + 1 < len(tokens):
            file_path = tokens[idx + 1]
            idx += 2
            continue
        if token == "--message" and idx + 1 < len(tokens):
            message = tokens[idx + 1]
            idx += 2
            continue
        if token in ("--title", "-h", "--help"):
            idx += 2 if token == "--title" and idx + 1 < len(tokens) else 1
            continue
        idx += 1
    if not file_path and not message:
        return None
    return repo, pr, file_path, message


def _cmd_mint(args: argparse.Namespace) -> int:
    path = mint_grant(args.repo, args.pr, args.file, args.message)
    print(f"OK: grant v2 written to {path}")
    print(f"  repo={args.repo} pr={args.pr} TTL=8h single-use")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    ok, err = verify_grant_for_append(
        args.repo,
        args.pr,
        args.file,
        args.message,
        consume=False,
    )
    if ok:
        print("OK: grant valid")
        return 0
    print(f"error: {err}", file=sys.stderr)
    return 1


def _cmd_consume(args: argparse.Namespace) -> int:
    ok, err = verify_grant_for_append(
        args.repo,
        args.pr,
        args.file,
        args.message,
        consume=True,
    )
    if ok:
        print("OK: grant consumed")
        return 0
    print(f"error: {err}", file=sys.stderr)
    return 1


def _cmd_reserve(args: argparse.Namespace) -> int:
    ok, err = reserve_grant_for_append(
        args.repo,
        args.pr,
        args.file,
        args.message,
    )
    if ok:
        print("OK: grant reserved")
        return 0
    print(f"error: {err}", file=sys.stderr)
    return 1


def _cmd_release(args: argparse.Namespace) -> int:
    ok, err = release_grant_for_append(
        args.repo,
        args.pr,
        args.file,
        args.message,
    )
    if ok:
        print("OK: grant reservation released")
        return 0
    print(f"error: {err}", file=sys.stderr)
    return 1


def _cmd_mark_applied(args: argparse.Namespace) -> int:
    ok, err = mark_remote_applied_for_append(
        args.repo,
        args.pr,
        args.file,
        args.message,
    )
    if ok:
        print("OK: remote mutation marked applied")
        return 0
    print(f"error: {err}", file=sys.stderr)
    return 1


def _cmd_reconcile(args: argparse.Namespace) -> int:
    try:
        remote_body = Path(args.remote_body_file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read remote body file: {exc}", file=sys.stderr)
        return 1
    if args.message is not None:
        append_block = args.message
    elif args.file:
        try:
            append_block = Path(args.file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot read append file: {exc}", file=sys.stderr)
            return 1
    else:
        print("error: provide --file or --message", file=sys.stderr)
        return 1
    if not follow_up_already_present(remote_body, append_block, args.title):
        return 2
    ok, err = reconcile_pending_consume(
        args.repo,
        args.pr,
        args.file,
        args.message,
        remote_body,
        args.title,
    )
    if ok:
        print("OK: grant reconciled and consumed")
        return 0
    print(f"error: {err}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PR-body operator grant v2")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_append_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--repo", required=True)
        p.add_argument("--pr", required=True)
        p.add_argument("--file")
        p.add_argument("--message")

    mint_p = sub.add_parser("mint")
    add_append_args(mint_p)
    mint_p.set_defaults(func=_cmd_mint)

    verify_p = sub.add_parser("verify")
    add_append_args(verify_p)
    verify_p.set_defaults(func=_cmd_verify)

    consume_p = sub.add_parser("consume")
    add_append_args(consume_p)
    consume_p.set_defaults(func=_cmd_consume)

    reserve_p = sub.add_parser("reserve")
    add_append_args(reserve_p)
    reserve_p.set_defaults(func=_cmd_reserve)

    release_p = sub.add_parser("release")
    add_append_args(release_p)
    release_p.set_defaults(func=_cmd_release)

    mark_p = sub.add_parser("mark-applied")
    add_append_args(mark_p)
    mark_p.set_defaults(func=_cmd_mark_applied)

    reconcile_p = sub.add_parser("reconcile")
    add_append_args(reconcile_p)
    reconcile_p.add_argument("--title", required=True)
    reconcile_p.add_argument("--remote-body-file", required=True)
    reconcile_p.set_defaults(func=_cmd_reconcile)

    args = parser.parse_args(argv)
    if args.command != "reconcile":
        if not args.file and not args.message:
            parser.error("provide --file or --message")
        if args.file and args.message:
            parser.error("provide --file or --message, not both")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
