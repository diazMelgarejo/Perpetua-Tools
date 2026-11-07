"""PT-owned pre-effect policy and durable duplicate suppression.

Claims have no expiry: a crash, cancellation or failed acknowledgement cannot
prove that a provider did no work. Operators reconcile unknown outcomes before
intentionally issuing a new scope. This is not a natural-language VISION parser.
Policy/verifier callbacks are trusted runtime configuration, never task metadata.

The identity is an exact goal envelope, not semantic similarity: automatically
generated job/session IDs are deliberately excluded. Explicit scopes distinguish
intentional independent work. Known model policy is enforced; implicit CLI model
configuration (``provider-default``) is not attested by this layer. Unknown model
tiers retain the canonical frugality gate's no-opinion behavior.

POSIX state directories must be user-owned and not writable by other users. The
file must be private and user-owned. Windows delegates to PT's existing allow-only
ACL helper; native Windows ACL behavior has not been qualified in this change.
POSIX mode bits make no claim about native Windows ACLs. SQLite reopens a pathname
after descriptor validation: trusted ancestors and same-user processes remain
an operational assumption; this is not a handle-relative filesystem sandbox.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable


class DuplicateDispatch(RuntimeError):
    """An equivalent dispatch already started, including an unknown outcome."""


@dataclass(frozen=True)
class DispatchRequest:
    """Effect identity; callers use an explicit scope for intentional new work."""

    scope: str
    provider: str
    model: str
    goal: str
    prompt: str
    role: str = ""
    constraints: str = ""
    task_type: str = "reasoning"
    privacy_critical: bool = False
    effort: str | None = None
    fast: bool | None = None

    def fingerprint(self) -> str:
        """Hash the complete envelope without persisting prompts or credentials."""
        if not self.scope.strip() or not self.provider.strip() or not self.model.strip():
            raise ValueError("dispatch scope, provider and model must be non-empty")
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DispatchPolicy:
    """Trusted policy result; ordinary permitted work needs no operator approval."""

    allowed: bool = True
    requires_operator_approval: bool = False
    reason: str = ""


PolicyEvaluator = Callable[[DispatchRequest], DispatchPolicy]
ApprovalVerifier = Callable[[DispatchRequest], bool]


class DispatchGuard:
    """Authorize and commit one cross-process claim immediately before an effect."""

    def __init__(
        self,
        state_dir: Path | str,
        *,
        policy: PolicyEvaluator | None = None,
        approval_verifier: ApprovalVerifier | None = None,
    ) -> None:
        """Bind PT state and trusted policy; never trust caller approval flags."""
        self.state_dir = Path(state_dir)
        self.policy = policy
        self.approval_verifier = approval_verifier

    def _authorize(self, request: DispatchRequest) -> None:
        """Reuse canonical frugality/model rules and fail closed on evaluation errors."""
        from orchestrator.gate import gate_permits, load_frugality_tier_by_name
        from perpetua_tools.model_governance import LaunchSpec, load_model_governance, plan_launch

        allowed, reason = gate_permits(
            load_frugality_tier_by_name().get(request.model),
            task_type=request.task_type,
            privacy_critical=request.privacy_critical,
        )
        if not allowed:
            raise PermissionError(reason)
        config = load_model_governance()
        if request.model in config.get("banned_launch_ids", ()):
            raise PermissionError("banned launch id")
        path = {"codex": "openai", "gemini": "google", "gemini-review": "google", "cursor": "cursor_grok_bot", "claude": "anthropic"}.get(request.provider)
        approval_required = False
        if path is not None and request.model != "provider-default":
            plan = plan_launch(LaunchSpec(path, request.model, effort=request.effort, fast=request.fast))
            approval_required = plan.requires_human_approval
        if self.policy is not None:
            decision = self.policy(request)
            if not isinstance(decision, DispatchPolicy):
                raise PermissionError("invalid runtime dispatch policy result")
            if not decision.allowed:
                raise PermissionError(decision.reason or "runtime dispatch policy denied")
            approval_required = approval_required or decision.requires_operator_approval
        if approval_required:
            if self.approval_verifier is None or self.approval_verifier(request) is not True:
                raise PermissionError("operator approval requires a trusted verifier")

    def _connect(self) -> sqlite3.Connection:
        """Open private durable state, refusing symlinks and unsafe database files."""
        from stat import S_ISDIR, S_ISREG, S_ISVTX

        if self.state_dir.is_symlink():
            raise PermissionError("dispatch state directory cannot be a symlink")
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            for ancestor in self.state_dir.absolute().parents:
                info = ancestor.lstat()
                # Root-owned sticky temporary directories protect user-owned
                # descendants from renaming by other unprivileged users.
                sticky_root = info.st_uid == 0 and bool(info.st_mode & S_ISVTX)
                if not S_ISDIR(info.st_mode) or info.st_uid not in {0, os.getuid()} or (info.st_mode & 0o022 and not sticky_root):
                    raise PermissionError("dispatch state ancestor must be a trusted directory")
        directory_info = self.state_dir.lstat()
        if not S_ISDIR(directory_info.st_mode):
            raise PermissionError("dispatch state directory must be a real directory")
        if os.name != "nt" and (directory_info.st_uid != os.getuid() or directory_info.st_mode & 0o022):
            raise PermissionError("dispatch state directory must be user-owned and not writable by others")
        if os.name == "nt":
            from orchestrator.alphaclaw_tls_proxy import _secure_path

            _secure_path(self.state_dir, is_directory=True)
        path = self.state_dir / "dispatch_claims.sqlite3"
        if path.is_symlink():
            raise PermissionError("dispatch ledger cannot be a symlink")
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            info = os.fstat(fd)
            named = path.lstat()
            if (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
                raise PermissionError("dispatch ledger changed while opening")
            if not S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PermissionError("dispatch ledger must be a private regular file")
            if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
                raise PermissionError("dispatch ledger permissions must be private")
        finally:
            os.close(fd)
        if os.name == "nt":
            _secure_path(path)
        connection = sqlite3.connect(path, timeout=2)
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    async def execute(
        self, request: DispatchRequest, effect: Callable[[], Awaitable[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Run at most once; never release claims after an ambiguous provider outcome."""
        fingerprint = request.fingerprint()
        self._authorize(request)
        connection = self._connect()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("CREATE TABLE IF NOT EXISTS dispatch_claims (fingerprint TEXT PRIMARY KEY, state TEXT NOT NULL)")
                cursor = connection.execute("INSERT OR IGNORE INTO dispatch_claims VALUES (?, 'started')", (fingerprint,))
                if cursor.rowcount != 1:
                    raise DuplicateDispatch("equivalent dispatch already claimed; reconcile its outcome before new work")
            try:
                result = await effect()
            except BaseException:
                with connection:
                    connection.execute("UPDATE dispatch_claims SET state='unknown' WHERE fingerprint=?", (fingerprint,))
                raise
            with connection:
                successful = result.get("ok", True) and result.get("status") not in {"failed", "error", "cancelled"}
                connection.execute("UPDATE dispatch_claims SET state=? WHERE fingerprint=?", ("succeeded" if successful else "unknown", fingerprint))
            return result
        finally:
            connection.close()
