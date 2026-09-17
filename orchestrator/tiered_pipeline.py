"""Governed Tier-5 pipeline execution for Perpetua-Tools.

The frugality router and gate remain the policy authorities. This module only
validates configured Tier-5 stages, sequences them after the canonical gate
permits execution, and delegates provider I/O to an injected dispatcher.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Mapping

import yaml

from orchestrator.gate import gate_permits, load_backend_by_name, load_frugality_tier_by_name

_log = logging.getLogger(__name__)

PIPELINE_TIER = 5
PIPELINE_FLAG = "PIPELINE_TIERED_ENABLED"
TRACE_PATH_ENV = "PT_PIPELINE_TRACE_PATH"
APPROVAL_DIR_ENV = "PT_PIPELINE_APPROVAL_DIR"
REVOKED_APPROVALS_ENV = "PT_PIPELINE_REVOKED_APPROVALS"
MAX_STAGES = 3
TRACE_ID_PATTERN = r"[A-Za-z0-9_-]+"
# Single source of truth for both enforcement paths -- fastapi_app.py's
# Pydantic Field(min_length=..., max_length=...) and validate_trace_id()
# below must agree, or a direct caller bypassing the HTTP layer could use a
# trace_id the API would reject (and vice versa).
TRACE_ID_MIN_LENGTH = 8
TRACE_ID_MAX_LENGTH = 128
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "pipelines.yml"
DEFAULT_MODELS = Path(__file__).resolve().parent.parent / "config" / "models.yml"
DEFAULT_TRACE = Path(__file__).resolve().parent.parent / ".state" / "frugality_pipeline.jsonl"
DEFAULT_APPROVAL_DIR = Path(__file__).resolve().parent.parent / ".state" / "pipeline_approvals"

_ALLOWED_TOP_LEVEL_KEYS = frozenset({"version", "enabled", "models", "recipes"})
_ALLOWED_RECIPE_KEYS = frozenset(
    {"stages", "max_total_tokens", "max_input_tokens", "cost_reservation_usd"}
)
_ALLOWED_STAGE_KEYS = frozenset({"name", "model", "max_tokens", "input_from", "instruction"})
_ALLOWED_MODEL_ALIAS_KEYS = frozenset({"candidates"})

@dataclass(frozen=True)
class DispatchResult:
    """Text plus whatever usage a provider reported for one dispatch call.

    ``total_tokens``/``cost_usd`` are ``None`` when a provider doesn't report
    usage at all, or reports a shape this code doesn't recognize -- this is
    telemetry, not a gate, so a provider's silence on usage must never block
    an otherwise-successful pipeline run.
    """

    text: str
    total_tokens: int | None
    cost_usd: float | None


Dispatcher = Callable[[str, str, int, str], Awaitable[DispatchResult]]


class PipelineError(RuntimeError):
    """Base error for governed Tier-5 pipeline execution."""


class PipelineDisabledError(PipelineError):
    """Raised when the explicit feature flag is not enabled."""


class PipelineConfigError(PipelineError):
    """Raised when pipeline configuration is invalid or incomplete."""


class PipelineApprovalError(PipelineError):
    """Raised when a required human-approval record is missing, expired,
    mismatched, or revoked.

    Deliberately NOT a subclass of PipelinePolicyError: the FastAPI endpoint's
    except-chain is type-ordered, and a subclass would be silently caught by
    the existing policy-denied handler, losing this error's distinct detail.
    """


class PipelinePolicyError(PipelineError):
    """Raised when the canonical frugality gate refuses Tier 5."""


class PipelineExecutionError(PipelineError):
    """Raised when an injected provider dispatcher cannot complete a stage."""


class PipelineCandidateUnavailableError(PipelineExecutionError):
    """Raised when one configured candidate is not currently dispatchable."""

    def __init__(self, message: str, *, fallback_safe: bool = True) -> None:
        super().__init__(message)
        self.fallback_safe = fallback_safe


def validate_trace_id(trace_id: str) -> str:
    """Validate the trace identifier at every approval boundary.

    The API applies the same rule through Pydantic, but direct callers must not
    rely on the HTTP layer to protect the approval artifact path.
    """
    if (
        not isinstance(trace_id, str)
        or not TRACE_ID_MIN_LENGTH <= len(trace_id) <= TRACE_ID_MAX_LENGTH
        or re.fullmatch(TRACE_ID_PATTERN, trace_id) is None
    ):
        raise PipelineApprovalError("invalid trace_id")
    return trace_id


def _reject_unknown_keys(obj: Mapping[str, object], allowed: frozenset[str], where: str) -> None:
    unknown = sorted(set(obj) - allowed)
    if unknown:
        raise PipelineConfigError("%s has unknown keys: %s" % (where, ", ".join(unknown)))


@dataclass(frozen=True)
class PipelineStage:
    name: str
    models: tuple[str, ...]
    max_tokens: int
    input_from: str | None = None
    instruction: str = ""

    @property
    def model(self) -> str:
        """Return the primary candidate for v1 callers expecting one model."""
        return self.models[0]


@dataclass(frozen=True)
class PipelineRecipe:
    name: str
    stages: tuple[PipelineStage, ...]
    max_total_tokens: int
    max_input_tokens: int
    cost_reservation_usd: float


@dataclass(frozen=True)
class PipelineApproval:
    """Human-bound authorization for one governed paid-pipeline run.

    An approval is never constructed from inline request fields at the
    execution boundary -- see ``load_pipeline_approval``/
    ``register_pipeline_approval``. Supporting both an inline-fields path and
    a separate-artifact path at the same endpoint would be a downgrade-attack
    shape: whichever path is weaker defines the system's real guarantee,
    since any misbehaving caller simply takes the easier one. Registration is
    a distinct action that must happen before execution, not a parameter of
    it.
    """

    trace_id: str
    approved_by: str
    purpose: str
    recipe: str
    route_tier: int
    max_tokens: int
    max_cost_usd: float
    expires_at: datetime
    scope: tuple[str, ...] = ()


@dataclass(frozen=True)
class PipelineResult:
    recipe: str
    output: str
    stage_outputs: Mapping[str, str]
    requested_tokens: int
    total_tokens_used: int | None
    total_cost_usd: float | None
    models_used: Mapping[str, str] = field(default_factory=dict)
    replay: bool = False


def tiered_pipeline_enabled(config_path: str | Path | None = None) -> bool:
    """Resolve an explicit env override, otherwise the canonical config default.

    ``PIPELINE_TIERED_ENABLED`` is deliberately override-only: leaving it
    unset keeps every runtime, config file, and deployment on the one checked-
    in ``config/pipelines.yml`` default rather than maintaining competing
    defaults in environment and YAML.
    """
    override = os.getenv(PIPELINE_FLAG)
    if override is not None:
        return override.strip() == "1"
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return False
    return isinstance(raw, Mapping) and raw.get("enabled") is True


def _input_token_upper_bound(value: str) -> int:
    """Conservatively bound tokens without a provider-specific tokenizer."""
    return len(value.encode("utf-8"))


def _approval_dir() -> Path:
    configured = os.getenv(APPROVAL_DIR_ENV, "").strip()
    return Path(configured) if configured else DEFAULT_APPROVAL_DIR


def _approval_artifact_path(directory: Path, trace_id: str) -> Path:
    """Resolve ``<directory>/<trace_id>.json``, rejecting any path escape.

    ``trace_id`` reaches this module from an HTTP request body. The FastAPI
    layer additionally restricts it to ``^[a-zA-Z0-9_-]+$`` (see
    ``fastapi_app.py``), but this check does not rely on that -- any caller
    of ``register_pipeline_approval``/``load_pipeline_approval`` with an
    untrusted trace_id (e.g. ``../../etc/cron.d/evil``) is still contained,
    defense-in-depth rather than a single point of failure.
    """
    validate_trace_id(trace_id)
    resolved_directory = directory.resolve()
    try:
        path = (resolved_directory / ("%s.json" % trace_id)).resolve()
    except (ValueError, OSError) as exc:
        # Belt-and-suspenders: validate_trace_id() above already rejects a
        # null byte (and everything else outside TRACE_ID_PATTERN) before
        # this line runs, so this branch shouldn't fire for any trace_id
        # that reaches here today. Kept in case TRACE_ID_PATTERN is ever
        # loosened, or some other OS/Path-level rejection isn't covered by
        # the regex -- translates that into the documented
        # PipelineApprovalError instead of a raw ValueError/OSError.
        raise PipelineApprovalError("invalid trace_id %r" % trace_id) from exc
    if not path.is_relative_to(resolved_directory):
        raise PipelineApprovalError("invalid trace_id %r escapes approval directory" % trace_id)
    return path


def register_pipeline_approval(
    approval: PipelineApproval, *, approval_dir: str | Path | None = None
) -> Path:
    """Persist an approval record as its own artifact.

    This is the only way an approval record comes into existence. There is no
    execution-time code path that builds one from inline request fields --
    registration is a distinct, prior action from execution.
    """
    directory = Path(approval_dir) if approval_dir is not None else _approval_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = _approval_artifact_path(directory, approval.trace_id)
    payload = {
        "trace_id": approval.trace_id,
        "approved_by": approval.approved_by,
        "purpose": approval.purpose,
        "recipe": approval.recipe,
        "route_tier": approval.route_tier,
        "max_tokens": approval.max_tokens,
        "max_cost_usd": approval.max_cost_usd,
        "expires_at": approval.expires_at.isoformat(),
        "scope": list(approval.scope),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_pipeline_approval(
    trace_id: str, *, approval_dir: str | Path | None = None
) -> PipelineApproval:
    """Load a previously-registered approval artifact by trace_id.

    A missing file, an unreadable file, and a malformed file are all
    intentionally indistinguishable from "no approval" -- every path here
    raises the same ``PipelineApprovalError`` so an unregistered trace_id and
    a corrupted handoff fail closed identically.
    """
    directory = Path(approval_dir) if approval_dir is not None else _approval_dir()
    path = _approval_artifact_path(directory, trace_id)
    if not path.is_file():
        raise PipelineApprovalError("no approval record found for trace_id %r" % trace_id)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineApprovalError(
            "approval record for trace_id %r is unreadable" % trace_id
        ) from exc
    if not isinstance(raw, dict):
        raise PipelineApprovalError(
            "approval record for trace_id %r must be a JSON object" % trace_id
        )
    try:
        # The artifact's own embedded trace_id must match the requested one --
        # they're looked up by the requested trace_id via the filename, but the
        # file's content is what actually becomes PipelineApproval.trace_id
        # below. If those ever diverge (tampering, a copy-paste artifact bug),
        # returning the file's value would silently authorize under the wrong
        # identity.
        embedded_trace_id = str(raw.get("trace_id", ""))
        if embedded_trace_id != trace_id:
            raise PipelineApprovalError(
                "approval record for trace_id %r has a mismatched embedded "
                "trace_id %r" % (trace_id, embedded_trace_id)
            )
        expires_at = datetime.fromisoformat(str(raw["expires_at"]))
        if expires_at.tzinfo is None:
            raise PipelineApprovalError(
                "approval record for trace_id %r has a timezone-naive expires_at" % trace_id
            )
        return PipelineApproval(
            trace_id=str(raw["trace_id"]),
            approved_by=str(raw["approved_by"]),
            purpose=str(raw["purpose"]),
            recipe=str(raw["recipe"]),
            route_tier=int(raw["route_tier"]),
            max_tokens=int(raw["max_tokens"]),
            max_cost_usd=float(raw["max_cost_usd"]),
            expires_at=expires_at,
            scope=tuple(str(item) for item in raw.get("scope", ())),
        )
    except PipelineApprovalError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineApprovalError(
            "approval record for trace_id %r is malformed" % trace_id
        ) from exc


class TieredPipelineRunner:
    """Load, validate, and execute a configured Tier-5 recipe.

    The runner has no provider client or credential handling. Its caller owns
    provider selection and passes an async dispatcher once a guarded pipeline
    run is appropriate.
    """

    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        models_path: str | Path | None = None,
        trace_path: str | Path | None = None,
    ) -> None:
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG
        self.models_path = Path(models_path) if models_path else DEFAULT_MODELS
        configured_trace_path = os.getenv(TRACE_PATH_ENV, "").strip()
        self.trace_path = (
            Path(trace_path)
            if trace_path is not None
            else Path(configured_trace_path)
            if configured_trace_path
            else DEFAULT_TRACE
        )
        self._models, self._recipes, self._model_backends = self._load_and_validate()

    @staticmethod
    def _load_revoked_trace_ids() -> frozenset[str]:
        """Read the revocation list fresh on every call, never cached.

        Caching this at __init__ time would mean a long-lived process (a
        uvicorn worker, a daemon) never observes a revocation appended to the
        file after construction -- an operator revoking a compromised or
        over-budget trace_id would have no effect until restart. The
        FastAPI endpoint already constructs a fresh runner per request, so
        this mainly matters for any other caller that reuses one instance,
        but the class itself should not depend on that calling convention.
        """
        revoked_path = os.getenv(REVOKED_APPROVALS_ENV, "").strip()
        if not revoked_path:
            return frozenset()
        # Distinct from "not configured" above: once an operator has pointed
        # at a path, that path must resolve to a readable file. Treating a
        # misconfigured path (missing, or a directory) the same as "no
        # revocation list configured" would silently degrade back to
        # "nothing is revoked" -- exactly the fail-open failure mode this
        # function exists to avoid.
        if not Path(revoked_path).is_file():
            raise PipelineApprovalError(
                "revocation file %r is not a readable file" % revoked_path
            )
        try:
            return frozenset(
                line.strip()
                for line in Path(revoked_path).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            )
        except OSError as exc:
            # Fail closed: an unreadable revocation file must block approval
            # validation, not silently behave as "nothing is revoked".
            raise PipelineApprovalError(
                "revocation file %r is unreadable" % revoked_path
            ) from exc

    def _load_and_validate(
        self,
    ) -> tuple[dict[str, tuple[str, ...]], dict[str, PipelineRecipe], dict[str, str]]:
        if not self.config_path.is_file():
            raise PipelineConfigError("pipeline config missing: %s" % self.config_path)
        if not self.models_path.is_file():
            raise PipelineConfigError("model registry missing: %s" % self.models_path)
        try:
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise PipelineConfigError("invalid pipeline config: %s" % exc) from exc
        if not isinstance(raw, dict):
            raise PipelineConfigError("pipeline config root must be a mapping")
        _reject_unknown_keys(raw, _ALLOWED_TOP_LEVEL_KEYS, "pipeline config root")
        if "enabled" in raw and not isinstance(raw["enabled"], bool):
            raise PipelineConfigError("pipeline config enabled must be a boolean")

        model_aliases = raw.get("models")
        recipe_rows = raw.get("recipes")
        if not isinstance(model_aliases, dict) or not model_aliases:
            raise PipelineConfigError("pipeline config requires a non-empty models mapping")
        if not isinstance(recipe_rows, dict) or not recipe_rows:
            raise PipelineConfigError("pipeline config requires a non-empty recipes mapping")

        # Model resolution is a hybrid: the config-literal alias is the
        # default, but an operator may override which registered model an
        # alias points at via PIPELINE_<ALIAS>_MODEL (e.g. PIPELINE_FAST_MODEL)
        # to canary a different Tier-5 model without a commit. The override
        # still names a model, not a raw provider string, so it goes through
        # the exact same frugality_tier==5 registry check below as the
        # config-literal default -- this restores the operational flexibility
        # an earlier, since-reverted design tried via unvalidated env-var
        # indirection, without reopening the registry-bypass gap that
        # motivated reverting it (see docs/next/2026-08-11-model-registry-provenance.md
        # and .agent/memory/working/2026-08-10-p4-tier5-pipeline-closure.md).
        models: dict[str, tuple[str, ...]] = {}
        for raw_alias, model_config in model_aliases.items():
            alias = str(raw_alias)
            if isinstance(model_config, str):
                candidates = [model_config.strip()]
            elif isinstance(model_config, Mapping):
                _reject_unknown_keys(
                    model_config,
                    _ALLOWED_MODEL_ALIAS_KEYS,
                    "pipeline model alias %r" % alias,
                )
                raw_candidates = model_config.get("candidates")
                if not isinstance(raw_candidates, list) or not raw_candidates:
                    raise PipelineConfigError(
                        "pipeline model alias %r requires a non-empty candidates list"
                        % alias
                    )
                candidates = [str(candidate).strip() for candidate in raw_candidates]
            else:
                raise PipelineConfigError(
                    "pipeline model alias %r must be a model name or candidates mapping"
                    % alias
                )
            if not candidates or any(not candidate for candidate in candidates):
                raise PipelineConfigError(
                    "pipeline model alias %r contains an empty candidate" % alias
                )
            override = os.getenv("PIPELINE_%s_MODEL" % alias.upper(), "").strip()
            if override:
                candidates = [override] + [
                    candidate for candidate in candidates if candidate != override
                ]
            models[alias] = tuple(dict.fromkeys(candidates))
        config_dir = str(self.models_path.parent)
        tiers = load_frugality_tier_by_name(config_dir)
        backends = load_backend_by_name(config_dir)
        model_backends: dict[str, str] = {}
        for alias, candidates in models.items():
            for model_name in candidates:
                tier = tiers.get(model_name)
                if tier != PIPELINE_TIER:
                    raise PipelineConfigError(
                        "pipeline model %s=%r must be frugality tier %d; found %r"
                        % (alias, model_name, PIPELINE_TIER, tier)
                    )
                backend = backends.get(model_name)
                if not isinstance(backend, str) or not backend.strip():
                    raise PipelineConfigError(
                        "pipeline model %s=%r is missing a backend in the model registry"
                        % (alias, model_name)
                    )
                model_backends[model_name] = backend.strip()

        recipes: dict[str, PipelineRecipe] = {}
        for recipe_name, recipe_row in recipe_rows.items():
            if not isinstance(recipe_row, dict):
                raise PipelineConfigError("recipe %r must be a mapping" % recipe_name)
            _reject_unknown_keys(recipe_row, _ALLOWED_RECIPE_KEYS, "recipe %r" % recipe_name)
            rows = recipe_row.get("stages")
            if not isinstance(rows, list) or not rows:
                raise PipelineConfigError("recipe %r requires non-empty stages" % recipe_name)
            if len(rows) > MAX_STAGES:
                raise PipelineConfigError(
                    "recipe %r has %d stages, exceeding the %d-stage limit"
                    % (recipe_name, len(rows), MAX_STAGES)
                )

            seen: set[str] = set()
            stages: list[PipelineStage] = []
            requested_tokens = 0
            for row in rows:
                if not isinstance(row, dict):
                    raise PipelineConfigError(
                        "recipe %r contains a non-mapping stage" % recipe_name
                    )
                _reject_unknown_keys(
                    row, _ALLOWED_STAGE_KEYS, "stage in recipe %r" % recipe_name
                )
                name = str(row.get("name", "")).strip()
                alias = str(row.get("model", "")).strip()
                if not name or name in seen:
                    raise PipelineConfigError(
                        "recipe %r has missing/duplicate stage name %r" % (recipe_name, name)
                    )
                if alias not in models:
                    raise PipelineConfigError(
                        "stage %r references unknown model alias %r" % (name, alias)
                    )
                try:
                    max_tokens = int(row.get("max_tokens", 0))
                except (TypeError, ValueError) as exc:
                    raise PipelineConfigError(
                        "stage %r max_tokens must be an integer" % name
                    ) from exc
                if max_tokens <= 0:
                    raise PipelineConfigError("stage %r max_tokens must be positive" % name)
                input_from = row.get("input_from")
                if input_from is not None:
                    input_from = str(input_from).strip()
                    if input_from not in seen:
                        raise PipelineConfigError(
                            "stage %r input_from must reference an earlier stage; got %r"
                            % (name, input_from)
                        )
                stages.append(
                    PipelineStage(
                        name=name,
                        models=models[alias],
                        max_tokens=max_tokens,
                        input_from=input_from,
                        instruction=str(row.get("instruction", "")).strip(),
                    )
                )
                seen.add(name)
                requested_tokens += max_tokens

            try:
                max_total_tokens = int(
                    recipe_row.get("max_total_tokens", requested_tokens)
                )
            except (TypeError, ValueError) as exc:
                raise PipelineConfigError(
                    "recipe %r max_total_tokens must be an integer" % recipe_name
                ) from exc
            try:
                max_input_tokens = int(
                    recipe_row.get("max_input_tokens", max_total_tokens)
                )
            except (TypeError, ValueError) as exc:
                raise PipelineConfigError(
                    "recipe %r max_input_tokens must be an integer" % recipe_name
                ) from exc
            if max_total_tokens <= 0 or max_input_tokens <= 0:
                raise PipelineConfigError("recipe %r token limits must be positive" % recipe_name)
            if requested_tokens > max_total_tokens:
                raise PipelineConfigError(
                    "recipe %r requests %d tokens but cap is %d"
                    % (recipe_name, requested_tokens, max_total_tokens)
                )
            try:
                cost_reservation_usd = float(recipe_row.get("cost_reservation_usd", 0))
            except (TypeError, ValueError) as exc:
                raise PipelineConfigError(
                    "recipe %r cost_reservation_usd must be a number" % recipe_name
                ) from exc
            if cost_reservation_usd <= 0:
                raise PipelineConfigError(
                    "recipe %r cost_reservation_usd must be positive" % recipe_name
                )
            recipes[str(recipe_name)] = PipelineRecipe(
                name=str(recipe_name),
                stages=tuple(stages),
                max_total_tokens=max_total_tokens,
                max_input_tokens=max_input_tokens,
                cost_reservation_usd=cost_reservation_usd,
            )

        return models, recipes, model_backends

    def _candidate_backend(self, model_name: str) -> str:
        backend = self._model_backends.get(model_name)
        if not backend:
            raise PipelineConfigError(
                "pipeline model %r is missing a backend in the model registry" % model_name
            )
        return backend

    def _candidate_is_in_scope(
        self, model_name: str, approval: PipelineApproval
    ) -> bool:
        backend = self._candidate_backend(model_name)
        allowed = frozenset(item.strip().lower() for item in approval.scope if item.strip())
        return backend.lower() in allowed

    def recipe(self, name: str) -> PipelineRecipe:
        try:
            return self._recipes[name]
        except KeyError as exc:
            raise PipelineConfigError("unknown pipeline recipe: %s" % name) from exc

    def _validate_approval(
        self, approval: PipelineApproval | None, *, recipe_name: str, recipe: PipelineRecipe
    ) -> None:
        if approval is None:
            raise PipelineApprovalError("pipeline approval is required")
        if approval.trace_id in self._load_revoked_trace_ids():
            raise PipelineApprovalError("approval trace_id %r has been revoked" % approval.trace_id)
        now = datetime.now(timezone.utc)
        if approval.expires_at.tzinfo is None:
            raise PipelineApprovalError("approval expires_at must be timezone-aware")
        if approval.expires_at <= now:
            raise PipelineApprovalError("pipeline approval is expired")
        if not all(
            value.strip() for value in (approval.trace_id, approval.approved_by, approval.purpose)
        ):
            raise PipelineApprovalError(
                "approval trace_id, approved_by, and purpose are required"
            )
        if approval.recipe != recipe_name:
            raise PipelineApprovalError("approval recipe does not match requested recipe")
        if approval.route_tier != PIPELINE_TIER:
            raise PipelineApprovalError(
                "approval must explicitly authorize route tier %d" % PIPELINE_TIER
            )
        if not approval.scope:
            raise PipelineApprovalError("approval provider/tool scope must be non-empty")
        if approval.max_tokens < recipe.max_total_tokens:
            raise PipelineApprovalError(
                "approval token budget is below the selected recipe ceiling"
            )
        if approval.max_cost_usd < recipe.cost_reservation_usd:
            raise PipelineApprovalError(
                "approval cost budget is below the configured recipe ceiling"
            )

    @staticmethod
    def _stage_prompt(
        original: str, stage: PipelineStage, outputs: Mapping[str, str]
    ) -> str:
        if stage.input_from is None:
            context = "Original request:\n%s" % original
        else:
            context = "Original request:\n%s\n\nOutput from stage %s:\n%s" % (
                original,
                stage.input_from,
                outputs[stage.input_from],
            )
        return "%s\n\n%s" % (stage.instruction, context) if stage.instruction else context

    def _emit_trace(
        self,
        *,
        recipe: str,
        stage: PipelineStage,
        model: str,
        elapsed_ms: int,
        status: str,
        trace_id: str,
        error_class: str | None,
        tokens_used: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        payload = {
            "timestamp": time.time(),
            "name": "tiered_pipeline.stage",
            "attributes": {
                "ot.tool.tier": PIPELINE_TIER,
                "pipeline.trace_id": trace_id,
                "pipeline.recipe": recipe,
                "pipeline.stage": stage.name,
                "pipeline.model": model,
                "pipeline.max_tokens": stage.max_tokens,
                "pipeline.tokens_used": tokens_used,
                "pipeline.cost_usd": cost_usd,
                "pipeline.error_class": error_class,
                "elapsed_ms": elapsed_ms,
                "status": status,
            },
        }
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

    async def run(
        self,
        recipe_name: str,
        prompt: str,
        *,
        approval: PipelineApproval,
        dispatch: Dispatcher,
        task_type: str = "reasoning",
        privacy_critical: bool = False,
        override_confirmed: bool = False,
        override_reason: str | None = None,
    ) -> PipelineResult:
        if not tiered_pipeline_enabled(self.config_path):
            raise PipelineDisabledError(
                "%s=1 is required for Tier-5 pipeline execution" % PIPELINE_FLAG
            )
        if not prompt.strip():
            raise PipelineError("pipeline prompt must be non-empty")

        # Recipe resolution moves above both the approval check and the gate
        # check (it used to sit after gate_permits) because approval
        # validation needs the recipe's own token/cost ceilings to check the
        # approval's budget against. Approval is validated before the
        # frugality gate on purpose: fail closed on "is a human on record for
        # this" before spending any cycles on "is this tier reachable right
        # now", and avoid leaking gate-specific denial detail (e.g. offline
        # state) to a caller who couldn't produce a valid approval anyway.
        recipe = self.recipe(recipe_name)
        self._validate_approval(approval, recipe_name=recipe_name, recipe=recipe)

        allowed, denied_reason = gate_permits(
            PIPELINE_TIER,
            task_type=task_type,
            privacy_critical=privacy_critical,
            override_confirmed=override_confirmed,
            override_reason=override_reason,
        )
        if not allowed:
            raise PipelinePolicyError(denied_reason or "canonical frugality gate denied Tier 5")

        outputs: dict[str, str] = {}
        models_used: dict[str, str] = {}
        requested_tokens = 0
        total_tokens_used: int | None = 0
        total_cost_usd: float | None = 0.0
        for stage in recipe.stages:
            stage_prompt = self._stage_prompt(prompt, stage, outputs)
            if _input_token_upper_bound(stage_prompt) > recipe.max_input_tokens:
                raise PipelinePolicyError(
                    "stage %s input exceeds max_input_tokens %d"
                    % (stage.name, recipe.max_input_tokens)
                )
            result: DispatchResult | None = None
            last_unavailable: PipelineCandidateUnavailableError | None = None
            has_in_scope_candidate = False
            for model in stage.models:
                started = time.monotonic()
                if not self._candidate_is_in_scope(model, approval):
                    self._emit_trace(
                        recipe=recipe.name,
                        stage=stage,
                        model=model,
                        elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                        status="skipped",
                        trace_id=approval.trace_id,
                        error_class="PipelineApprovalError",
                    )
                    continue
                has_in_scope_candidate = True
                try:
                    result = await dispatch(model, stage_prompt, stage.max_tokens, stage.name)
                except PipelineCandidateUnavailableError as exc:
                    if not exc.fallback_safe:
                        self._emit_trace(
                            recipe=recipe.name,
                            stage=stage,
                            model=model,
                            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                            status="failed",
                            trace_id=approval.trace_id,
                            error_class=type(exc).__name__,
                        )
                        raise
                    last_unavailable = exc
                    self._emit_trace(
                        recipe=recipe.name,
                        stage=stage,
                        model=model,
                        elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                        status="unavailable",
                        trace_id=approval.trace_id,
                        error_class=type(exc).__name__,
                    )
                    continue
                except Exception as exc:
                    self._emit_trace(
                        recipe=recipe.name,
                        stage=stage,
                        model=model,
                        elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                        status="failed",
                        trace_id=approval.trace_id,
                        error_class=type(exc).__name__,
                    )
                    raise
                models_used[stage.name] = model
                break
            if result is None:
                if not has_in_scope_candidate:
                    raise PipelineApprovalError(
                        "stage %r has no candidate within approval scope %s"
                        % (stage.name, list(approval.scope))
                    )
                raise PipelineExecutionError(
                    "stage %r has no available configured model" % stage.name
                ) from last_unavailable
            output = result.text
            if not isinstance(output, str) or not output.strip():
                raise PipelineExecutionError(
                    "stage %r returned an empty/non-text result" % stage.name
                )
            outputs[stage.name] = output
            requested_tokens += stage.max_tokens
            # A partial sum would misrepresent the true total, so any stage
            # missing usage data collapses the running total to None for the
            # rest of the run -- this is telemetry, never a gate, so it never
            # raises.
            if result.total_tokens is None or total_tokens_used is None:
                total_tokens_used = None
            else:
                total_tokens_used += result.total_tokens
            if result.cost_usd is None or total_cost_usd is None:
                total_cost_usd = None
            else:
                total_cost_usd += result.cost_usd
            self._emit_trace(
                recipe=recipe.name,
                stage=stage,
                model=models_used[stage.name],
                elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                status="completed",
                trace_id=approval.trace_id,
                error_class=None,
                tokens_used=result.total_tokens,
                cost_usd=result.cost_usd,
            )

        if total_cost_usd is not None and total_cost_usd > recipe.cost_reservation_usd:
            _log.warning(
                "tier5 pipeline %r actual cost $%.4f exceeded configured reservation $%.4f",
                recipe.name,
                total_cost_usd,
                recipe.cost_reservation_usd,
            )

        return PipelineResult(
            recipe=recipe.name,
            output=outputs[recipe.stages[-1].name],
            stage_outputs=dict(outputs),
            requested_tokens=requested_tokens,
            total_tokens_used=total_tokens_used,
            total_cost_usd=total_cost_usd,
            models_used=dict(models_used),
        )
