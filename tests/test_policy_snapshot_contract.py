"""Policy snapshots must be valid and reused by the real registry route."""

import json

import pytest

import orchestrator.fastapi_app as fa
import orchestrator.model_registry as mr
import orchestrator.policy_stacks as ps


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"lane_qualification": {"status": "blocked"}},
        {"ordered_candidates": []},
        {"ordered_candidates": None},
        {"ordered_candidates": {}},
        {"ordered_candidates": "not-a-list"},
        {"ordered_candidates": [None]},
        {"ordered_candidates": [{}]},
        {"ordered_candidates": [{"model_id": ""}]},
    ],
)
def test_invalid_catalog_is_an_unavailable_snapshot(tmp_path, monkeypatch, document):
    """Exercise the real file loader and production snapshot error boundary."""
    (tmp_path / ps.POLICY_FILENAME).write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(ps, "_config_dir", lambda: tmp_path)
    monkeypatch.setattr(fa, "load_free_first_policy", ps.load_policy)

    snapshot, error = fa._load_policy_snapshot()

    assert snapshot is None
    assert "ordered_candidates" in error


@pytest.mark.parametrize("document", [[], None, "invalid", 1])
def test_non_object_policy_still_fails_closed(tmp_path, monkeypatch, document):
    """Preserve the existing JSON-object requirement."""
    (tmp_path / ps.POLICY_FILENAME).write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(ps, "_config_dir", lambda: tmp_path)
    monkeypatch.setattr(fa, "load_free_first_policy", ps.load_policy)

    snapshot, error = fa._load_policy_snapshot()

    assert snapshot is None
    assert "JSON object" in error


def test_valid_catalog_snapshot_is_preserved(tmp_path, monkeypatch):
    """Schema validation must not open a blocked lane or qualify a candidate."""
    document = {
        "lane_qualification": {"status": "blocked"},
        "ordered_candidates": [
            {"model_id": "glm-4.7-flash", "pricing_status": "free",
             "qualification_status": "unqualified"},
        ],
    }
    (tmp_path / ps.POLICY_FILENAME).write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(ps, "_config_dir", lambda: tmp_path)
    monkeypatch.setattr(fa, "load_free_first_policy", ps.load_policy)

    snapshot, error = fa._load_policy_snapshot()

    assert snapshot == document
    assert error == ""


@pytest.mark.parametrize(
    "model_ids",
    [["openrouter/free"], ["glm-4.5-flash", "glm-4.7-flash"]],
)
def test_real_route_task_reuses_policy_snapshot(tmp_path, monkeypatch, model_ids):
    """The real route method must use supplied rows without reloading policy."""
    (tmp_path / "devices.yml").write_text("devices: {}\n", encoding="utf-8")
    (tmp_path / "models.yml").write_text("models: []\n", encoding="utf-8")
    (tmp_path / "routing.yml").write_text(
        "routes:\n  default:\n    roles: [general]\n", encoding="utf-8"
    )
    monkeypatch.setenv("PT_DISABLE_LIVE_MODEL_PROBES", "1")
    monkeypatch.setattr(mr, "is_offline_mode", lambda: False)
    snapshot = {
        "lane_qualification": {"status": "open"},
        "ordered_candidates": [
            {"model_id": model_id, "pricing_status": "free",
             "qualification_status": "qualified"}
            for model_id in model_ids
        ],
    }
    reloads = []

    def unexpected_reload():
        reloads.append(True)
        return {
            "ordered_candidates": [
                {"model_id": "glm-4-flash-250414", "pricing_status": "free"},
            ],
        }

    monkeypatch.setattr(mr, "load_policy", unexpected_reload)
    registry = mr.ModelRegistry(config_dir=str(tmp_path))

    chain = registry.route_task("default", policy=snapshot)

    assert [candidate.name for candidate in chain] == model_ids
    assert reloads == [], "route_task must not reload a supplied policy snapshot"
