"""Integration coverage for the explicit paid Tier-5 control-plane route."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import orchestrator.fastapi_app as app_module
from orchestrator.model_transport import ProviderTransportRegistry
from orchestrator.tiered_pipeline import (
    PipelineApproval,
    PipelineApprovalError,
    PipelineResult,
    TieredPipelineRunner,
)
from orchestrator.tier5_budget import (
    BudgetConflictError,
    BudgetInsufficientError,
    BudgetUnavailableError,
    MICROUSD_PER_USD,
    Reservation,
    Tier5BudgetLedger,
)
from orchestrator.tier5_execution import (
    HMAC_KEY_ENV,
    Tier5ExecutionService,
)


def _valid_approval(**overrides: object) -> PipelineApproval:
    fields: dict[str, object] = {
        "trace_id": "endpoint-test-trace",
        "approved_by": "operator@example.com",
        "purpose": "integration test",
        "recipe": "classify_then_generate",
        "route_tier": 5,
        "max_tokens": 8192,
        "max_cost_usd": 0.25,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "scope": ("openrouter",),
    }
    fields.update(overrides)
    return PipelineApproval(**fields)


class _Runner:
    captured_run_kwargs: dict[str, object] = {}

    def recipe(self, name: str):
        assert name == "classify_then_generate"
        return type("Recipe", (), {"cost_reservation_usd": 0.25, "name": "classify_then_generate"})()

    async def run(self, recipe_name, prompt, **kwargs):
        assert recipe_name == "classify_then_generate"
        assert prompt == "do the work"
        assert callable(kwargs["dispatch"])
        _Runner.captured_run_kwargs = kwargs
        return PipelineResult(
            recipe=recipe_name,
            output="final answer",
            stage_outputs={"classify": "internal", "generate": "final answer"},
            requested_tokens=512,
            total_tokens_used=480,
            total_cost_usd=0.1,
        )


class _RunnerRaisesApprovalError:
    def recipe(self, name: str):
        return type("Recipe", (), {"cost_reservation_usd": 0.25, "name": "classify_then_generate"})()

    async def run(self, recipe_name, prompt, **kwargs):
        raise PipelineApprovalError("approval is expired")


class _Transport:
    async def dispatch(self, model, prompt, max_tokens, stage):
        return type("DispatchRes", (), {"text": "mock output", "total_tokens": 100, "cost_usd": 0.05})()


@pytest.fixture
def test_ledger(tmp_path: Path) -> Tier5BudgetLedger:
    return Tier5BudgetLedger(
        tmp_path / "endpoint_budget.db",
        daily_limit_microusd=10 * MICROUSD_PER_USD,
    )


@pytest.fixture
def control_plane_client(monkeypatch, test_ledger: Tier5BudgetLedger):
    previous_overrides = app_module.app.dependency_overrides.copy()
    _Runner.captured_run_kwargs.clear()
    monkeypatch.setenv("ORAMA_INSECURE_DEV", "0")
    monkeypatch.setenv("ORAMA_CONTROL_PLANE_TOKEN", "pt-test-token")
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.setenv(HMAC_KEY_ENV, "test-endpoint-hmac-key")
    app_module.app.dependency_overrides[app_module.get_tiered_pipeline_runner] = _Runner
    app_module.app.dependency_overrides[app_module.get_provider_transport] = _Transport
    app_module.app.dependency_overrides[app_module.get_tier5_budget_ledger] = lambda: test_ledger
    try:
        with TestClient(app_module.app, raise_server_exceptions=False) as client:
            yield client
    finally:
        _Runner.captured_run_kwargs.clear()
        app_module.app.dependency_overrides.clear()
        app_module.app.dependency_overrides.update(previous_overrides)


@pytest.mark.integration
def test_pipeline_run_requires_control_plane_auth(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": "any-trace"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_pipeline_run_requires_idempotency_key_header(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": "any-trace"},
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 422
    assert "Idempotency-Key" in response.json()["detail"]


@pytest.mark.integration
def test_pipeline_run_rejects_non_uuid4_idempotency_key(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": "any-trace"},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": "invalid-not-a-uuid4",
        },
    )
    assert response.status_code == 422
    assert "UUIDv4" in response.json()["detail"]


@pytest.mark.integration
def test_pipeline_run_returns_final_output_without_internal_stage_payload(
    control_plane_client, monkeypatch
) -> None:
    approval = _valid_approval()
    monkeypatch.setattr(app_module, "load_pipeline_approval", lambda trace_id: approval)
    key = str(uuid.uuid4())

    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": key,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["recipe"] == "classify_then_generate"
    assert body["output"] == "final answer"
    assert body["requested_tokens"] == 512
    assert body["cost_reservation_usd"] == 0.25
    assert body["held_microusd"] == 0
    assert body["settled_microusd"] == int(0.1 * MICROUSD_PER_USD)
    assert body["run_id"] == f"run-{key}"
    assert _Runner.captured_run_kwargs["approval"] is approval


@pytest.mark.integration
def test_pipeline_run_idempotent_replay_returns_existing_state(
    control_plane_client, monkeypatch
) -> None:
    approval = _valid_approval()
    monkeypatch.setattr(app_module, "load_pipeline_approval", lambda trace_id: approval)
    key = str(uuid.uuid4())

    resp1 = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": key,
        },
    )
    assert resp1.status_code == 200

    resp2 = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": key,
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["run_id"] == f"run-{key}"
    assert resp2.json()["status"] == "completed"


@pytest.mark.integration
def test_pipeline_run_idempotency_conflict_returns_409(
    control_plane_client, monkeypatch
) -> None:
    approval = _valid_approval()
    monkeypatch.setattr(app_module, "load_pipeline_approval", lambda trace_id: approval)
    key = str(uuid.uuid4())

    resp1 = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": key,
        },
    )
    assert resp1.status_code == 200

    resp2 = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "different prompt", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": key,
        },
    )
    assert resp2.status_code == 409
    assert "conflicts" in resp2.json()["detail"]


@pytest.mark.integration
def test_pipeline_run_insufficient_budget_returns_402(
    control_plane_client, monkeypatch, tmp_path
) -> None:
    approval = _valid_approval()
    monkeypatch.setattr(app_module, "load_pipeline_approval", lambda trace_id: approval)
    # Zero limit ledger
    tiny_ledger = Tier5BudgetLedger(
        tmp_path / "tiny_budget.db",
        daily_limit_microusd=100,  # Only 100 microUSD = $0.0001
    )
    app_module.app.dependency_overrides[app_module.get_tier5_budget_ledger] = lambda: tiny_ledger

    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 402
    assert "Daily budget cannot cover" in response.json()["detail"]


@pytest.mark.integration
def test_pipeline_run_status_endpoint(
    control_plane_client, monkeypatch, test_ledger: Tier5BudgetLedger
) -> None:
    approval = _valid_approval()
    monkeypatch.setattr(app_module, "load_pipeline_approval", lambda trace_id: approval)
    key = str(uuid.uuid4())
    run_id = f"run-{key}"

    # Pre-check: 404 before run
    get_resp = control_plane_client.get(
        f"/pipelines/runs/{run_id}",
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert get_resp.status_code == 404

    # Run pipeline
    run_resp = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": key,
        },
    )
    assert run_resp.status_code == 200

    # Status check after run
    status_resp = control_plane_client.get(
        f"/pipelines/runs/{run_id}",
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert status_body["run_id"] == run_id
    assert status_body["state"] == "SETTLED"
    assert status_body["held_microusd"] == 0
    assert status_body["settled_microusd"] == int(0.1 * MICROUSD_PER_USD)


@pytest.mark.integration
def test_pipeline_run_fails_closed_when_feature_is_disabled(control_plane_client, monkeypatch) -> None:
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "0")
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": "any-trace"},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Tier-5 pipelines are disabled"


@pytest.mark.integration
def test_pipeline_run_requires_trace_id_in_request_body(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work"},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 422


@pytest.mark.integration
def test_pipeline_run_rejects_unregistered_trace_id(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": "never-registered"},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Pipeline approval invalid, expired, or revoked"


@pytest.mark.integration
def test_pipeline_run_maps_runner_approval_error_to_403(control_plane_client, monkeypatch) -> None:
    approval = _valid_approval()
    monkeypatch.setattr(app_module, "load_pipeline_approval", lambda trace_id: approval)
    app_module.app.dependency_overrides[app_module.get_tiered_pipeline_runner] = (
        _RunnerRaisesApprovalError
    )

    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Pipeline approval invalid, expired, or revoked"


@pytest.mark.integration
def test_pipeline_run_maps_transport_error_to_502_or_503(control_plane_client, monkeypatch) -> None:
    approval = _valid_approval()
    monkeypatch.setattr(app_module, "load_pipeline_approval", lambda trace_id: approval)

    class _RunnerTransportError:
        def recipe(self, name: str):
            return type("Recipe", (), {"cost_reservation_usd": 0.25, "name": "classify_then_generate"})()

        async def run(self, *args, **kwargs):
            raise app_module.ProviderTransportError("network down", retryable=False)

    app_module.app.dependency_overrides[app_module.get_tiered_pipeline_runner] = _RunnerTransportError

    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 502

    class _RunnerRetryableTransportError:
        def recipe(self, name: str):
            return type("Recipe", (), {"cost_reservation_usd": 0.25, "name": "classify_then_generate"})()

        async def run(self, *args, **kwargs):
            raise app_module.ProviderTransportError("rate limit", retryable=True)

    app_module.app.dependency_overrides[app_module.get_tiered_pipeline_runner] = _RunnerRetryableTransportError

    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 503


@pytest.mark.integration
def test_pipeline_run_maps_config_and_execution_errors_to_503(control_plane_client, monkeypatch) -> None:
    approval = _valid_approval()
    monkeypatch.setattr(app_module, "load_pipeline_approval", lambda trace_id: approval)

    class _RunnerExecutionError:
        def recipe(self, name: str):
            return type("Recipe", (), {"cost_reservation_usd": 0.25, "name": "classify_then_generate"})()

        async def run(self, *args, **kwargs):
            raise app_module.PipelineExecutionError("stage failed")

    app_module.app.dependency_overrides[app_module.get_tiered_pipeline_runner] = _RunnerExecutionError

    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 503


@pytest.mark.integration
def test_register_approval_requires_control_plane_auth(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/approvals",
        json={
            "trace_id": "t1-auth-check",
            "approved_by": "op",
            "purpose": "p",
            "recipe": "classify_then_generate",
            "route_tier": 5,
            "max_tokens": 8192,
            "max_cost_usd": 0.25,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "scope": ["openrouter"],
        },
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_register_approval_then_run_end_to_end(control_plane_client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PT_PIPELINE_APPROVAL_DIR", str(tmp_path / "approvals"))

    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    register_response = control_plane_client.post(
        "/pipelines/approvals",
        json={
            "trace_id": "e2e-trace",
            "approved_by": "operator@example.com",
            "purpose": "end to end test",
            "recipe": "classify_then_generate",
            "route_tier": 5,
            "max_tokens": 8192,
            "max_cost_usd": 0.25,
            "expires_at": expires_at,
            "scope": ["openrouter"],
        },
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert register_response.status_code == 200
    assert register_response.json()["trace_id"] == "e2e-trace"

    run_response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": "e2e-trace"},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert run_response.status_code == 200
    assert _Runner.captured_run_kwargs["approval"].trace_id == "e2e-trace"


@pytest.mark.integration
def test_register_approval_rejects_naive_expires_at(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/approvals",
        json={
            "trace_id": "t2-naive-expiry",
            "approved_by": "op",
            "purpose": "p",
            "recipe": "classify_then_generate",
            "route_tier": 5,
            "max_tokens": 8192,
            "max_cost_usd": 0.25,
            "expires_at": datetime.now().isoformat(),  # naive, no offset
            "scope": ["openrouter"],
        },
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize(
    "malicious_trace_id",
    [
        "../../etc/cron.d/evil",
        "../escape",
        "..\\escape",
        "/etc/passwd",
        "a/../../b",
        "has spaces",
        "control\x00char",
        "short",  # also exercises min_length=8 in the same parametrized pass
    ],
)
def test_register_approval_rejects_malicious_trace_id(
    control_plane_client, malicious_trace_id, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("PT_PIPELINE_APPROVAL_DIR", str(tmp_path / "approvals"))
    response = control_plane_client.post(
        "/pipelines/approvals",
        json={
            "trace_id": malicious_trace_id,
            "approved_by": "op",
            "purpose": "p",
            "recipe": "classify_then_generate",
            "route_tier": 5,
            "max_tokens": 8192,
            "max_cost_usd": 0.25,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "scope": ["openrouter"],
        },
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 422
    assert not any((tmp_path).glob("**/*.json"))


@pytest.mark.integration
@pytest.mark.parametrize(
    "malicious_trace_id",
    ["../../etc/cron.d/evil", "../escape", "a/../../b"],
)
def test_pipeline_run_rejects_malicious_trace_id(
    control_plane_client, malicious_trace_id
) -> None:
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": malicious_trace_id},
        headers={
            "Authorization": "Bearer pt-test-token",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 422
