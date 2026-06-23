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
            "http://192.168.254.108:1234",
            preferred=WIN_ONLY,
            platform="win",
        )

    assert resolved == WIN_ONLY
