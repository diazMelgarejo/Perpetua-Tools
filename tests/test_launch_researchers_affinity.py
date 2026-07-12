"""Regression tests for hardware-affinity enforcement in launch_researchers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_LAUNCH_RESEARCHERS = REPO_ROOT / "scripts" / "launch_researchers.py"


def _load_launch_researchers():
    spec = importlib.util.spec_from_file_location("launch_researchers", _LAUNCH_RESEARCHERS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    for path in (REPO_ROOT / "src", REPO_ROOT):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def launch_researchers():
    return _load_launch_researchers()


@pytest.fixture(autouse=True)
def clear_policy_cache(monkeypatch):
    import utils.hardware_policy as hw

    monkeypatch.setenv("PT_DISABLE_LIVE_MODEL_PROBES", "1")
    hw._POLICY_CACHE = None
    yield
    hw._POLICY_CACHE = None


WIN_ONLY = "Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2"
GEMMA_WIN_ONLY = "gemma-4-26B-A4B-it-Q4_K_M"
MAC_SAFE = "Qwen3.5-9B-MLX-4bit"


def test_platform_for_role():
    lr = _load_launch_researchers()
    assert lr._platform_for_role("mac-researcher") == "mac"
    assert lr._platform_for_role("win-researcher") == "win"


def test_pick_model_with_affinity_skips_never_mac(launch_researchers):
    chosen = launch_researchers._pick_model_with_affinity(
        [WIN_ONLY, MAC_SAFE],
        preferred="missing-model",
        platform="mac",
        backend_label="LM Studio",
    )
    assert chosen == MAC_SAFE


def test_pick_model_with_affinity_rejects_all_forbidden_on_mac(launch_researchers):
    chosen = launch_researchers._pick_model_with_affinity(
        [WIN_ONLY],
        preferred=WIN_ONLY,
        platform="mac",
        backend_label="LM Studio",
    )
    assert chosen is None


@pytest.mark.asyncio
async def test_resolve_lmstudio_model_filters_never_mac_proxy(launch_researchers):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": WIN_ONLY}, {"id": MAC_SAFE}],
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(launch_researchers.httpx, "AsyncClient", return_value=mock_client):
        resolved = await launch_researchers._resolve_lmstudio_model(
            "http://localhost:1234",
            preferred="missing-model",
            platform="mac",
        )

    assert resolved == MAC_SAFE


@pytest.mark.asyncio
async def test_resolve_lmstudio_model_rejects_preferred_never_mac_when_listed(launch_researchers):
    """LM Studio proxy lists Win-only models on Mac — preferred must not bypass affinity."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": WIN_ONLY}, {"id": MAC_SAFE}],
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(launch_researchers.httpx, "AsyncClient", return_value=mock_client):
        resolved = await launch_researchers._resolve_lmstudio_model(
            "http://localhost:1234",
            preferred=WIN_ONLY,
            platform="mac",
        )

    assert resolved == MAC_SAFE


@pytest.mark.asyncio
async def test_run_researcher_passes_win_platform_to_resolver(launch_researchers):
    with patch.object(
        launch_researchers,
        "_resolve_lmstudio_model",
        new=AsyncMock(return_value="resolved-model"),
    ) as mock_resolve:
        with patch.object(launch_researchers, "tracker") as mock_tracker:
            mock_tracker.register.return_value = MagicMock(agent_id="test-agent")
            with patch.object(launch_researchers, "_append_event"):
                await launch_researchers.run_researcher(
                    role="win-researcher",
                    endpoint="http://127.0.1.1:1234",
                    model="some-model",
                    backend="lmstudio-win",
                    task="test",
                    loop_once=True,
                    interval=1,
                    rounds=0,
                )

    mock_resolve.assert_awaited_once_with(
        "http://127.0.1.1:1234",
        "some-model",
        platform="win",
    )


@pytest.mark.asyncio
async def test_resolve_lmstudio_model_filters_gemma_quant_alias_on_mac(launch_researchers):
    """LM Studio uses quant-suffixed ids; aliases must enforce NEVER_MAC."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": GEMMA_WIN_ONLY}, {"id": MAC_SAFE}],
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(launch_researchers.httpx, "AsyncClient", return_value=mock_client):
        resolved = await launch_researchers._resolve_lmstudio_model(
            "http://localhost:1234",
            preferred=GEMMA_WIN_ONLY,
            platform="mac",
        )

    assert resolved == MAC_SAFE


@pytest.mark.asyncio
async def test_resolve_lmstudio_model_allows_win_only_on_win(launch_researchers):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": [{"id": WIN_ONLY}]}
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(launch_researchers.httpx, "AsyncClient", return_value=mock_client):
        resolved = await launch_researchers._resolve_lmstudio_model(
            "http://127.0.1.1:1234",
            preferred=WIN_ONLY,
            platform="win",
        )

    assert resolved == WIN_ONLY
