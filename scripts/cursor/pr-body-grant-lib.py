#!/usr/bin/env python3
"""HMAC-bound operator grant for append-pr-body.sh (grant v2).

Same-user Keychain HMAC is escalation control, not cryptographic human identity.
WebAuthn / MCP approval is deferred to security-sentinel v2.1.
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


def _canonical_payload(
    repo: str,
    pr_number: str,
    nonce: str,
    issued_at: str,
    action: str,
    content_digest: str,
) -> bytes:
    payload = (
        f"grant-v2|{repo}|{pr_number}|{nonce}|{issued_at}|{action}|{content_digest}"
    )
    return payload.encode("utf-8")


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


def _write_fallback_secret_file(secret: str) -> None:
    FALLBACK_SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(FALLBACK_SECRET_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(secret)
        handle.write("\n")


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


def _lock_nonce_state() -> tuple[Any, dict[str, Any]]:
    NONCE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = open(NONCE_STATE_PATH, "a+", encoding="utf-8")
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
    return handle, state


def _write_nonce_state(handle: Any, state: dict[str, Any]) -> None:
    handle.seek(0)
    handle.truncate()
    json.dump(state, handle)
    handle.flush()
    os.fsync(handle.fileno())


def _prune_nonce_state(state: dict[str, Any]) -> None:
    nonces = state.get("nonces", {})
    cutoff = _now_utc().timestamp() - GRANT_TTL_SECONDS
    for nonce, ts in list(nonces.items()):
        parsed = _parse_timestamp(str(ts))
        if parsed is None:
            del nonces[nonce]
            continue
        if parsed.timestamp() < cutoff:
            del nonces[nonce]
    state["nonces"] = nonces


def nonce_is_consumed(nonce: str) -> bool:
    handle, state = _lock_nonce_state()
    try:
        _prune_nonce_state(state)
        return nonce in state["nonces"]
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def consume_nonce_atomic(nonce: str) -> bool:
    """Mark nonce consumed once. Returns False if already consumed."""
    handle, state = _lock_nonce_state()
    try:
        _prune_nonce_state(state)
        if nonce in state["nonces"]:
            return False
        state["nonces"][nonce] = _now_utc().isoformat().replace("+00:00", "Z")
        _write_nonce_state(handle, state)
        return True
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def verify_grant_fields(
    fields: dict[str, str],
    repo: str,
    pr_number: str,
    content_digest: str,
    action: str = DEFAULT_ACTION,
    check_nonce_consumed: bool = True,
) -> tuple[bool, str]:
    if fields.get("marker") != GRANT_MARKER:
        if "operator-grant-v1" in str(fields):
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
        if not consume_nonce_atomic(nonce):
            return False, "grant nonce already consumed (replay blocked)"
        try:
            ACK_PATH.unlink(missing_ok=True)
        except OSError as exc:
            return False, f"failed to remove consumed grant file: {exc}"

    return True, ""


def mint_grant(
    repo: str,
    pr_number: str,
    file_path: str | None,
    message: str | None,
    cwd: Path | None = None,
) -> Path:
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
    fd = os.open(str(ACK_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(body)
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

    args = parser.parse_args(argv)
    if not args.file and not args.message:
        parser.error("provide --file or --message")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
