"""Parametrized fixtures for display_state derivation from confidence thresholds."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest import FixtureRequest


class DisplayState(str, Enum):
    UNKNOWN = "UNKNOWN"
    SUSPECT = "SUSPECT"
    DEGRADED = "DEGRADED"
    HEALTHY = "HEALTHY"


CONFIDENCE_TO_DISPLAY_STATE = [
    (0.0, DisplayState.UNKNOWN),
    (0.3, DisplayState.SUSPECT),
    (0.7, DisplayState.DEGRADED),
    (1.0, DisplayState.HEALTHY),
]


def _confidence_state_id(param: tuple[float, DisplayState]) -> str:
    confidence, state = param
    return f"confidence={confidence}-state={state.value}"


@pytest.fixture(params=CONFIDENCE_TO_DISPLAY_STATE, ids=_confidence_state_id)
def confidence_state_pair(request: FixtureRequest) -> tuple[float, DisplayState]:
    """Return a single (confidence_threshold, expected_display_state) pair."""
    return request.param


@pytest.fixture
def confidence_threshold(confidence_state_pair: tuple[float, DisplayState]) -> float:
    """Confidence threshold under test."""
    return confidence_state_pair[0]


@pytest.fixture
def expected_display_state(confidence_state_pair: tuple[float, DisplayState]) -> DisplayState:
    """Expected UI display_state for the paired confidence threshold."""
    return confidence_state_pair[1]
