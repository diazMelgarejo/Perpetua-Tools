"""Three-way structured-server-apply (SSA) merge planner for oramaclaw V1.

``plan_resource`` compares, per managed JSON-Pointer field:

- **base**     — what the owning manager last recorded in the store registry
                 (``None`` if the field has never been claimed)
- **observed** — the value currently present in the live ``openclaw.json``
- **desired**  — the value the manifest wants for this field

and produces a :class:`MergePlan` of :class:`FieldAction` records (one per
managed path) plus any :class:`Conflict` records that require operator input.

Resolution policy (evaluated per field):

1. ``desired == observed``                 → ``skip``       (already correct)
2. ``base is None``                         → ``apply``      (first adoption)
3. ``observed == base``                     → ``apply``      (clean, desired wins)
4. ``policy == STRICT``                     → ``conflict``   (strict never weaves)
5. security topology (DELEGATION /
   EXECUTION_POLICY) **or** ``policy ==
   CONFLICT``                               → ``conflict``   (never auto-weave)
6. ``policy == COOPERATIVE``                → respect a matching store override
                                              (``skip``/``apply``) else
                                              ``auto_weave``
7. anything else                            → ``conflict``

**Security topology rule:** ``DELEGATION`` and ``EXECUTION_POLICY`` resources
ALWAYS conflict on drift, even under a cooperative policy. Kind is checked
before the cooperative branch.

No raw secrets are handled here — only field values and their SHA-256
fingerprints (auth material is reference-only at the manifest boundary).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from oramaclaw.store import _fingerprint
from oramaclaw.types import Conflict, MergePolicy, Resource, ResourceKind

# Kinds whose drift is part of the security topology and must never be
# auto-woven (they always escalate to an operator-resolved conflict).
_SECURITY_KINDS: frozenset[ResourceKind] = frozenset(
    {ResourceKind.DELEGATION, ResourceKind.EXECUTION_POLICY}
)

# Standard conflict resolution choices surfaced to the CLI / portal.
_CONFLICT_CHOICES: tuple[str, ...] = ("apply-desired", "keep-current", "show-diff")


# ── Plan dataclasses ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FieldAction:
    """The planned action for a single managed JSON-Pointer field."""
    managed_path: str
    kind: Literal["apply", "skip", "auto_weave", "conflict"]
    desired_value: Any   # value to write; None for skip / conflict
    fingerprint: str     # fingerprint of desired_value


@dataclass(frozen=True)
class MergePlan:
    """The full plan for one resource across all of its managed paths."""
    resource_key: str
    actions: tuple[FieldAction, ...]    # one per managed_path
    conflicts: tuple[Conflict, ...]
    auto_woven: tuple[str, ...]         # managed_path strings auto-woven


# ── Field extraction ──────────────────────────────────────────────────────────

def extract_field(config: dict, json_pointer: str) -> Any:
    """Return the value at ``json_pointer`` inside ``config``, or ``None``.

    Implements RFC 6901-style traversal over nested ``dict`` (and ``list``)
    structures using only the standard library. A root pointer (``""``)
    returns the whole document. Any missing segment yields ``None``.
    """
    if json_pointer == "":
        return config

    if not json_pointer.startswith("/"):
        # Tolerate a leading-slash-less pointer for robustness.
        json_pointer = "/" + json_pointer

    current: Any = config
    # Skip the empty first element produced by the leading slash.
    for raw_token in json_pointer.split("/")[1:]:
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return None
            current = current[token]
        elif isinstance(current, list):
            try:
                index = int(token)
            except ValueError:
                return None
            if index < 0 or index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


# ── Planning ──────────────────────────────────────────────────────────────────

def resource_key(resource: Resource) -> str:
    """Stable key for a resource: ``<kind>:<identifier>``."""
    return f"{resource.kind.value}:{resource.identifier}"


def _conflict(
    rkey: str,
    resource: Resource,
    managed_path: str,
    base_fp: str | None,
    observed_fp: str | None,
    desired_fp: str,
    *,
    security: bool,
) -> Conflict:
    return Conflict(
        resource_key=rkey,
        manager=resource.manager,
        managed_path=managed_path,
        base_fingerprint=base_fp,
        observed_fingerprint=observed_fp,
        desired_fingerprint=desired_fp,
        security_topology=security,
        choices=_CONFLICT_CHOICES,
        resolution_id=f"{rkey}{managed_path}#{desired_fp[:12]}",
    )


def plan_resource(resource: Resource, live_config: dict, store: Any) -> MergePlan:
    """Compute the three-way SSA merge plan for ``resource``.

    ``live_config`` is the raw ``openclaw.json`` document (as returned by
    ``gateway_config_get().configuration``). ``store`` must provide:

    - ``field_fingerprint(resource_key, managed_path) -> str | None``
    - ``get_auto_weave_override(resource_key, managed_path) -> dict | None``
      (a dict with ``source_field_fingerprint`` and ``observed_value`` keys)
    """
    rkey = resource_key(resource)
    is_security = resource.kind in _SECURITY_KINDS

    actions: list[FieldAction] = []
    conflicts: list[Conflict] = []
    auto_woven: list[str] = []

    for path in resource.managed_paths:
        desired = _spec_value(resource.spec, path)
        desired_fp = _fingerprint(desired)
        observed = extract_field(live_config, path)
        base_fp = store.field_fingerprint(rkey, path)

        # 1. Already correct — no write needed.
        if desired == observed:
            actions.append(FieldAction(path, "skip", None, desired_fp))
            continue

        # 2. First adoption — claim the field outright.
        if base_fp is None:
            actions.append(FieldAction(path, "apply", desired, desired_fp))
            continue

        observed_fp = _fingerprint(observed)

        # 3. Clean: manager still owns it (observed matches recorded base).
        if observed_fp == base_fp:
            actions.append(FieldAction(path, "apply", desired, desired_fp))
            continue

        # --- Field has drifted away from the recorded base. ---

        # 4. STRICT never auto-weaves.
        if resource.policy == MergePolicy.STRICT:
            conflicts.append(
                _conflict(rkey, resource, path, base_fp, observed_fp, desired_fp, security=False)
            )
            actions.append(FieldAction(path, "conflict", None, desired_fp))
            continue

        # 5. Security topology or explicit CONFLICT policy never auto-weaves.
        if is_security or resource.policy == MergePolicy.CONFLICT:
            conflicts.append(
                _conflict(
                    rkey, resource, path, base_fp, observed_fp, desired_fp,
                    security=is_security,
                )
            )
            actions.append(FieldAction(path, "conflict", None, desired_fp))
            continue

        # 6. COOPERATIVE — respect a still-valid override, else auto-weave.
        if resource.policy == MergePolicy.COOPERATIVE:
            override = store.get_auto_weave_override(rkey, path)
            if override is not None and override.get("source_field_fingerprint") == desired_fp:
                # The drift was previously accepted for THIS desired value.
                effective = override.get("observed_value")
                if effective == observed:
                    actions.append(FieldAction(path, "skip", None, desired_fp))
                else:
                    # Live has changed since the override was recorded — the
                    # override baseline is stale. Escalate to conflict rather
                    # than silently overwriting the newer live value.
                    conflicts.append(
                        _conflict(rkey, resource, path, base_fp, observed_fp, desired_fp, security=False)
                    )
                    actions.append(FieldAction(path, "conflict", None, desired_fp))
                continue

            # No override, or the source field changed → re-weave the drift.
            actions.append(FieldAction(path, "auto_weave", observed, observed_fp))
            auto_woven.append(path)
            continue

        # 7. Fallback — any other mismatch escalates to a conflict.
        conflicts.append(
            _conflict(rkey, resource, path, base_fp, observed_fp, desired_fp, security=is_security)
        )
        actions.append(FieldAction(path, "conflict", None, desired_fp))

    return MergePlan(
        resource_key=rkey,
        actions=tuple(actions),
        conflicts=tuple(conflicts),
        auto_woven=tuple(auto_woven),
    )


def _spec_value(spec: Any, json_pointer: str) -> Any:
    """Read the desired value for ``json_pointer`` from a resource spec.

    The spec may either mirror the live document structure (nested under the
    full pointer) or store the value under the pointer's final token. Both
    layouts are supported; the nested form is preferred.
    """
    nested = extract_field(dict(spec), json_pointer)
    if nested is not None:
        return nested
    if json_pointer and json_pointer != "":
        leaf = json_pointer.rstrip("/").split("/")[-1]
        if leaf in spec:
            return spec[leaf]
    return nested
