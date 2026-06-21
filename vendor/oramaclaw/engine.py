"""Control-plane apply engine for oramaclaw V1.

``ControlEngine.apply_manifest()`` drives a single declarative-apply transaction:

1. Acquire the per-target PID lock (via ``ControlStore.open``).
2. Fetch live config from the gateway; fall back to a restricted offline
   transport if the gateway is unreachable.
3. Plan each resource against the live config (``oramaclaw.merge.plan_resource``).
4. Accumulate a config patch from ``apply`` actions, record auto-weave
   overrides, and durably stage conflicts as ``PendingResolution`` records.
5. Apply the merged patch through the gateway, retrying once on a stale-hash
   rejection.
6. Journal every phase (``prepared`` → ``applied_unverified`` → final state).

The final state is one of: ``committed``, ``auto_woven``, ``conflicted``,
``needs_input``, ``gateway_unavailable``, ``failed``.

P2-2 cooperative timer: the 90-second budget is per *apply invocation*, not
per resource.  When elapsed wall time since step 1 exceeds 90 s and the plan
produced any ``auto_weave`` actions, those auto-weave actions are downgraded
to conflicts (they must then go through operator resolution).  The clock is
injectable so the downgrade is testable; in normal synchronous applies the
elapsed time is well under the budget and nothing is downgraded.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable, Mapping

from oramaclaw.merge import plan_resource
from oramaclaw.store import ControlStore
from oramaclaw.transport import OfflineTransport, make_transport
from oramaclaw.types import (
    Conflict,
    ConfigTarget,
    ControlManifest,
    ControlResult,
    GatewayUnavailable,
    OpenClawTransport,
    PendingResolution,
    StaleConfiguration,
)

_log = logging.getLogger(__name__)

# Per-apply-invocation cooperative budget (P2-2). Beyond this, auto-weave
# actions downgrade to conflicts and require operator resolution.
COOPERATIVE_TIMEOUT_SECONDS = 90.0


def _iso_now() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ── Interaction strategies (portal vs headless) ──────────────────────────────

class NoResponseInteraction:
    """Auto-weave path: no portal available, so resolution never arrives."""

    def wait_for_resolution(self, conflict: Conflict, timeout_seconds: float) -> str | None:
        return None  # always auto-weave


class PortalInteraction:
    """Async wait: poll the store until a portal/CLI resolves the conflict.

    Polls ``store.pending_by_id(conflict.resolution_id)`` every
    ``poll_interval`` seconds until the record carries a ``chosen`` value or
    ``timeout_seconds`` elapses.
    """

    def __init__(self, store: ControlStore, poll_interval: float = 2.0) -> None:
        self._store = store
        self._poll_interval = poll_interval

    def wait_for_resolution(self, conflict: Conflict, timeout_seconds: float) -> str | None:
        deadline = time.monotonic() + timeout_seconds
        while True:
            record = self._store.pending_by_id(conflict.resolution_id)
            if record and record.get("chosen") is not None:
                return record["chosen"]
            if time.monotonic() >= deadline:
                return None
            remaining = deadline - time.monotonic()
            time.sleep(min(self._poll_interval, max(0.0, remaining)))


# ── Engine ────────────────────────────────────────────────────────────────────

class ControlEngine:
    """Applies a parsed ``ControlManifest`` to a target configuration.

    ``transport`` may be injected (for tests / pre-probed callers); when None,
    ``make_transport(target)`` is invoked at apply time.  ``clock`` returns a
    monotonic-ish wall time in seconds and is injectable so the cooperative
    timer (P2-2) can be exercised deterministically.
    """

    def __init__(
        self,
        transport: OpenClawTransport | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._transport = transport
        self._clock = clock or time.monotonic

    # -- public API -----------------------------------------------------------

    def apply_manifest(
        self,
        manifest: ControlManifest,
        target: ConfigTarget,
    ) -> ControlResult:
        transaction_id = uuid.uuid4().hex
        started = self._clock()

        with ControlStore.open(target) as store:
            try:
                return self._apply_locked(manifest, target, store, transaction_id, started)
            except Exception as exc:  # noqa: BLE001 — convert any failure to a result + journal
                _log.exception("apply_manifest failed: %s", exc)
                store.append_journal(
                    transaction_id, "failed", [], [], [],
                    extra={"error": str(exc)},
                )
                return ControlResult(
                    transaction_id=transaction_id,
                    state="failed",
                    applied=(),
                    auto_woven=(),
                    conflicts=(),
                    warnings=(f"apply failed: {exc}",),
                )

    # -- internals ------------------------------------------------------------

    def _apply_locked(
        self,
        manifest: ControlManifest,
        target: ConfigTarget,
        store: ControlStore,
        transaction_id: str,
        started: float,
    ) -> ControlResult:
        warnings: list[str] = []

        # 1. Resolve a transport (inject or probe).
        transport: OpenClawTransport = self._transport or make_transport(target)

        # 2. Fetch live config; fall back to offline on GatewayUnavailable.
        gateway_unavailable = False
        try:
            live = transport.gateway_config_get(target)
        except GatewayUnavailable as exc:
            _log.warning("gateway unavailable on config get: %s; falling back to offline", exc)
            warnings.append("gateway unavailable; offline fallback engaged")
            transport = OfflineTransport()
            gateway_unavailable = True
            live = transport.gateway_config_get(target)

        live_config: Mapping[str, Any] = live.configuration
        base_hash = live.base_hash

        # 3. Journal: prepared.
        store.append_journal(
            transaction_id, "prepared", [], [], [],
            extra={"resource_count": len(manifest.resources)},
        )

        # 4. Plan every resource and bucket the field actions.
        merged_patch: dict[str, Any] = {}
        applied_keys: list[str] = []
        auto_woven_pairs: list[str] = []
        conflicts: list[Conflict] = []

        for resource in manifest.resources:
            plan = plan_resource(resource, live_config, store)
            resource_key = plan.resource_key
            applied_this_resource = False

            for action in plan.actions:
                kind = action.kind
                if kind == "apply":
                    self._set_path(merged_patch, action.managed_path, action.desired_value)
                    store.record_ownership(
                        resource.manager,
                        resource_key,
                        action.managed_path,
                        action.desired_value,
                    )
                    applied_this_resource = True
                elif kind == "auto_weave":
                    # Honor the cooperative budget (P2-2): past 90 s, an
                    # auto-weave becomes a conflict requiring operator input.
                    if (self._clock() - started) > COOPERATIVE_TIMEOUT_SECONDS:
                        conflicts.append(
                            self._conflict_from_action(resource_key, resource.manager, action)
                        )
                        store.add_pending(
                            self._pending_from_action(
                                resource_key, resource.manager, action, transaction_id
                            )
                        )
                        warnings.append(
                            f"auto-weave downgraded to conflict (>90s): "
                            f"{resource_key}{action.managed_path}"
                        )
                        continue
                    self._set_path(merged_patch, action.managed_path, action.desired_value)
                    store.record_ownership(
                        resource.manager,
                        resource_key,
                        action.managed_path,
                        action.desired_value,
                    )
                    auto_woven_pairs.append(f"{resource_key}{action.managed_path}")
                    applied_this_resource = True
                elif kind == "conflict":
                    conflict = self._conflict_from_action(resource_key, resource.manager, action)
                    conflicts.append(conflict)
                    store.add_pending(
                        PendingResolution(
                            resolution_id=conflict.resolution_id,
                            conflict=conflict,
                            transaction_id=transaction_id,
                            created_at=_iso_now(),
                        )
                    )
                else:  # "skip" — no-op
                    continue

            # Plan-level conflicts (not represented as field actions).
            for conflict in plan.conflicts:
                if conflict not in conflicts:
                    conflicts.append(conflict)
                    store.add_pending(
                        PendingResolution(
                            resolution_id=conflict.resolution_id,
                            conflict=conflict,
                            transaction_id=transaction_id,
                            created_at=_iso_now(),
                        )
                    )

            if applied_this_resource:
                applied_keys.append(resource_key)

        # 5. Apply the merged patch (retry once on a stale hash).
        if merged_patch:
            try:
                transport.gateway_config_apply(target, merged_patch, base_hash)
            except StaleConfiguration:
                # Re-fetch live config and re-plan every resource against the
                # fresh state before retrying. Avoids silently overwriting
                # concurrent mutations that arrived between the initial fetch
                # and the first apply attempt.
                fresh = transport.gateway_config_get(target)
                live_config = fresh.configuration
                base_hash = fresh.base_hash
                merged_patch = {}
                applied_keys = []
                auto_woven_pairs = []
                conflicts = []
                for resource in manifest.resources:
                    plan = plan_resource(resource, live_config, store)
                    resource_key = plan.resource_key
                    applied_this_resource = False
                    for action in plan.actions:
                        kind = action.kind
                        if kind == "apply":
                            self._set_path(merged_patch, action.managed_path, action.desired_value)
                            store.record_ownership(
                                resource.manager,
                                resource_key,
                                action.managed_path,
                                action.desired_value,
                            )
                            applied_this_resource = True
                        elif kind == "auto_weave":
                            self._set_path(merged_patch, action.managed_path, action.desired_value)
                            store.record_ownership(
                                resource.manager,
                                resource_key,
                                action.managed_path,
                                action.desired_value,
                            )
                            auto_woven_pairs.append(f"{resource_key}{action.managed_path}")
                            applied_this_resource = True
                        elif kind == "conflict":
                            conflict = self._conflict_from_action(resource_key, resource.manager, action)
                            conflicts.append(conflict)
                            store.add_pending(
                                PendingResolution(
                                    resolution_id=conflict.resolution_id,
                                    conflict=conflict,
                                    transaction_id=transaction_id,
                                    created_at=_iso_now(),
                                )
                            )
                    for conflict in plan.conflicts:
                        if conflict not in conflicts:
                            conflicts.append(conflict)
                            store.add_pending(
                                PendingResolution(
                                    resolution_id=conflict.resolution_id,
                                    conflict=conflict,
                                    transaction_id=transaction_id,
                                    created_at=_iso_now(),
                                )
                            )
                    if applied_this_resource:
                        applied_keys.append(resource_key)
                if merged_patch:
                    transport.gateway_config_apply(target, merged_patch, base_hash)
            except GatewayUnavailable as exc:
                _log.warning("gateway unavailable on apply: %s", exc)
                warnings.append(f"gateway unavailable on apply: {exc}")
                gateway_unavailable = True
                # Nothing committed remotely; clear applied bookkeeping.
                applied_keys = []
                auto_woven_pairs = []
            else:
                # 6. Journal: applied but not yet verified.
                store.append_journal(
                    transaction_id, "applied_unverified", applied_keys, auto_woven_pairs, [],
                )

        # 7. Determine final state, journal, and return.
        state = self._determine_state(
            applied_keys, auto_woven_pairs, conflicts, gateway_unavailable
        )
        store.append_journal(
            transaction_id,
            state,
            applied_keys,
            auto_woven_pairs,
            [c.resolution_id for c in conflicts],
        )
        return ControlResult(
            transaction_id=transaction_id,
            state=state,
            applied=tuple(applied_keys),
            auto_woven=tuple(auto_woven_pairs),
            conflicts=tuple(conflicts),
            warnings=tuple(warnings),
        )

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _determine_state(
        applied_keys: list[str],
        auto_woven_pairs: list[str],
        conflicts: list[Conflict],
        gateway_unavailable: bool,
    ) -> str:
        any_progress = bool(applied_keys) or bool(auto_woven_pairs)
        if conflicts:
            return "conflicted" if any_progress else "needs_input"
        if gateway_unavailable and not any_progress:
            return "gateway_unavailable"
        if auto_woven_pairs:
            return "auto_woven"
        if applied_keys:
            return "committed"
        # No actions at all — treat an empty manifest as a clean commit.
        return "committed"

    @staticmethod
    def _set_path(patch: dict[str, Any], managed_path: str, value: Any) -> None:
        """Insert ``value`` at a JSON-Pointer-style ``managed_path`` into ``patch``."""
        parts = [p for p in managed_path.split("/") if p != ""]
        if not parts:
            return
        cursor = patch
        for part in parts[:-1]:
            nxt = cursor.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                cursor[part] = nxt
            cursor = nxt
        cursor[parts[-1]] = value

    @staticmethod
    def _conflict_from_action(resource_key: str, manager: str, action: Any) -> Conflict:
        return Conflict(
            resource_key=resource_key,
            manager=manager,
            managed_path=action.managed_path,
            base_fingerprint=None,
            observed_fingerprint=None,
            desired_fingerprint=getattr(action, "fingerprint", "") or "",
            security_topology=False,
            choices=("apply-desired", "keep-current", "show-diff"),
            resolution_id=f"{resource_key}{action.managed_path}#{(getattr(action, 'fingerprint', '') or '')[:12]}",
        )

    @classmethod
    def _pending_from_action(
        cls,
        resource_key: str,
        manager: str,
        action: Any,
        transaction_id: str,
    ) -> PendingResolution:
        conflict = cls._conflict_from_action(resource_key, manager, action)
        return PendingResolution(
            resolution_id=conflict.resolution_id,
            conflict=conflict,
            transaction_id=transaction_id,
            created_at=_iso_now(),
        )
