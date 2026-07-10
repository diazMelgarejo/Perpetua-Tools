"""Parametrized fixtures for ``StateTransitionManager`` edge cases (E1-E10).

Fixtures are intentionally decoupled from the concrete ``StateTransitionManager``
implementation. Wire the ``state_transition_manager`` fixture to the real class
once it exists; the parametrized edge-case tables below can stay unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pytest import FixtureRequest


class TransitionState(str, Enum):
    """Canonical states used by ``StateTransitionManager`` edge-case fixtures."""

    IDLE = "IDLE"
    COUNTING = "COUNTING"
    THRESHOLD_REACHED = "THRESHOLD_REACHED"
    RECOVERING = "RECOVERING"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class EdgeCaseId(str, Enum):
    """Identifiers for the ten scaffolded edge cases."""

    E1_MID_BATCH_THRESHOLD = "E1_MID_BATCH_THRESHOLD"
    E2_BATCH_BOUNDARY_TOGGLE = "E2_BATCH_BOUNDARY_TOGGLE"
    E3_RECOVERY_BEFORE_COMMIT = "E3_RECOVERY_BEFORE_COMMIT"
    E4_RECOVERY_AFTER_COMMIT = "E4_RECOVERY_AFTER_COMMIT"
    E5_COUNTER_RESET_AT_ZERO = "E5_COUNTER_RESET_AT_ZERO"
    E6_COUNTER_RESET_AT_THRESHOLD = "E6_COUNTER_RESET_AT_THRESHOLD"
    E7_DEGENERATE_EMPTY_INPUT = "E7_DEGENERATE_EMPTY_INPUT"
    E8_DEGENERATE_NEGATIVE_INPUT = "E8_DEGENERATE_NEGATIVE_INPUT"
    E9_DEGENERATE_NAN_INPUT = "E9_DEGENERATE_NAN_INPUT"
    E10_DEGENERATE_OVERFLOW_INPUT = "E10_DEGENERATE_OVERFLOW_INPUT"


@dataclass(frozen=True)
class BatchConfig:
    """Batch parameters for a transition scenario.

    Attributes:
        size: Total number of items in the batch.
        threshold: Counter value required to trigger a state transition.
        midpoint: Index at which the threshold is crossed mid-batch.
    """

    size: int
    threshold: int
    midpoint: int


@dataclass(frozen=True)
class TransitionScenario:
    """A single edge-case scenario for ``StateTransitionManager``.

    Attributes:
        edge_case_id: Human-readable identifier, e.g. ``EdgeCaseId.E1_*``.
        description: What the scenario exercises.
        initial_state: Starting state of the manager.
        inputs: Sequence of values fed into the manager.
        batch_config: Optional batch sizing / threshold configuration.
        expected_state: State expected after processing ``inputs``.
        expected_counter: Expected internal counter value after processing.
        expect_error: Whether the scenario is expected to raise an exception.
        error_type: Expected exception type when ``expect_error`` is True.
    """

    edge_case_id: EdgeCaseId
    description: str
    initial_state: TransitionState
    inputs: tuple[Any, ...]
    batch_config: BatchConfig | None
    expected_state: TransitionState
    expected_counter: int
    expect_error: bool = False
    error_type: type[BaseException] | None = None


# ---------------------------------------------------------------------------
# Edge-case catalogue: E1-E10
# ---------------------------------------------------------------------------

MID_BATCH_SCENARIOS: list[TransitionScenario] = [
    TransitionScenario(
        edge_case_id=EdgeCaseId.E1_MID_BATCH_THRESHOLD,
        description="Threshold crossed in the middle of a batch; state flips early.",
        initial_state=TransitionState.COUNTING,
        inputs=(1, 1, 1, 1, 1),
        batch_config=BatchConfig(size=5, threshold=3, midpoint=2),
        expected_state=TransitionState.THRESHOLD_REACHED,
        expected_counter=5,
    ),
    TransitionScenario(
        edge_case_id=EdgeCaseId.E2_BATCH_BOUNDARY_TOGGLE,
        description="Counter lands exactly on batch boundary then drops back below.",
        initial_state=TransitionState.COUNTING,
        inputs=(1, 1, 1, -1, -1),
        batch_config=BatchConfig(size=5, threshold=3, midpoint=2),
        expected_state=TransitionState.COUNTING,
        expected_counter=1,
    ),
]

RECOVERY_SCENARIOS: list[TransitionScenario] = [
    TransitionScenario(
        edge_case_id=EdgeCaseId.E3_RECOVERY_BEFORE_COMMIT,
        description="Recovery signal arrives before the threshold commit point.",
        initial_state=TransitionState.COUNTING,
        inputs=(1, 1, -1, 1, 1),
        batch_config=BatchConfig(size=5, threshold=3, midpoint=2),
        expected_state=TransitionState.RECOVERING,
        expected_counter=2,
    ),
    TransitionScenario(
        edge_case_id=EdgeCaseId.E4_RECOVERY_AFTER_COMMIT,
        description="Recovery signal arrives after threshold was already committed.",
        initial_state=TransitionState.THRESHOLD_REACHED,
        inputs=(-1, -1, -1),
        batch_config=BatchConfig(size=3, threshold=3, midpoint=0),
        expected_state=TransitionState.RECOVERING,
        expected_counter=0,
    ),
]

COUNTER_RESET_SCENARIOS: list[TransitionScenario] = [
    TransitionScenario(
        edge_case_id=EdgeCaseId.E5_COUNTER_RESET_AT_ZERO,
        description="Explicit reset while counter is already zero is a no-op.",
        initial_state=TransitionState.IDLE,
        inputs=("__reset__",),
        batch_config=None,
        expected_state=TransitionState.IDLE,
        expected_counter=0,
    ),
    TransitionScenario(
        edge_case_id=EdgeCaseId.E6_COUNTER_RESET_AT_THRESHOLD,
        description="Reset immediately after threshold clears committed state.",
        initial_state=TransitionState.THRESHOLD_REACHED,
        inputs=("__reset__",),
        batch_config=BatchConfig(size=1, threshold=1, midpoint=0),
        expected_state=TransitionState.IDLE,
        expected_counter=0,
    ),
]

DEGENERATE_INPUT_SCENARIOS: list[TransitionScenario] = [
    TransitionScenario(
        edge_case_id=EdgeCaseId.E7_DEGENERATE_EMPTY_INPUT,
        description="Empty input batch leaves state and counter unchanged.",
        initial_state=TransitionState.IDLE,
        inputs=(),
        batch_config=BatchConfig(size=0, threshold=1, midpoint=-1),
        expected_state=TransitionState.IDLE,
        expected_counter=0,
    ),
    TransitionScenario(
        edge_case_id=EdgeCaseId.E8_DEGENERATE_NEGATIVE_INPUT,
        description="Negative increment is clamped or recorded as recovery signal.",
        initial_state=TransitionState.COUNTING,
        inputs=(-5,),
        batch_config=BatchConfig(size=1, threshold=3, midpoint=-1),
        expected_state=TransitionState.RECOVERING,
        expected_counter=0,
    ),
    TransitionScenario(
        edge_case_id=EdgeCaseId.E9_DEGENERATE_NAN_INPUT,
        description="Non-numeric input raises a controlled validation error.",
        initial_state=TransitionState.COUNTING,
        inputs=(float("nan"),),
        batch_config=BatchConfig(size=1, threshold=3, midpoint=-1),
        expected_state=TransitionState.ERROR,
        expected_counter=0,
        expect_error=True,
        error_type=ValueError,
    ),
    TransitionScenario(
        edge_case_id=EdgeCaseId.E10_DEGENERATE_OVERFLOW_INPUT,
        description="Overflow-sized increment saturates or errors predictably.",
        initial_state=TransitionState.COUNTING,
        inputs=(2**63,),
        batch_config=BatchConfig(size=1, threshold=3, midpoint=-1),
        expected_state=TransitionState.THRESHOLD_REACHED,
        expected_counter=2**63,
    ),
]

ALL_EDGE_CASES: list[TransitionScenario] = [
    *MID_BATCH_SCENARIOS,
    *RECOVERY_SCENARIOS,
    *COUNTER_RESET_SCENARIOS,
    *DEGENERATE_INPUT_SCENARIOS,
]


def _edge_case_id(scenario: TransitionScenario) -> str:
    """Return a stable pytest node id for a ``TransitionScenario``."""
    return scenario.edge_case_id.value


# ---------------------------------------------------------------------------
# Parametrized fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(params=MID_BATCH_SCENARIOS, ids=_edge_case_id)
def mid_batch_scenario(request: FixtureRequest) -> TransitionScenario:
    """Parametrized fixture covering E1-E2 mid-batch threshold transitions."""
    return request.param  # type: ignore[no-any-return]


@pytest.fixture(params=RECOVERY_SCENARIOS, ids=_edge_case_id)
def recovery_scenario(request: FixtureRequest) -> TransitionScenario:
    """Parametrized fixture covering E3-E4 recovery timing cases."""
    return request.param  # type: ignore[no-any-return]


@pytest.fixture(params=COUNTER_RESET_SCENARIOS, ids=_edge_case_id)
def counter_reset_scenario(request: FixtureRequest) -> TransitionScenario:
    """Parametrized fixture covering E5-E6 counter reset cases."""
    return request.param  # type: ignore[no-any-return]


@pytest.fixture(params=DEGENERATE_INPUT_SCENARIOS, ids=_edge_case_id)
def degenerate_input_scenario(request: FixtureRequest) -> TransitionScenario:
    """Parametrized fixture covering E7-E10 degenerate input cases."""
    return request.param  # type: ignore[no-any-return]


@pytest.fixture(params=ALL_EDGE_CASES, ids=_edge_case_id)
def transition_scenario(request: FixtureRequest) -> TransitionScenario:
    """Parametrized fixture covering all E1-E10 edge cases."""
    return request.param  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Convenience decomposition fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def edge_case_id(transition_scenario: TransitionScenario) -> EdgeCaseId:
    """Edge-case identifier under test."""
    return transition_scenario.edge_case_id


@pytest.fixture
def initial_state(transition_scenario: TransitionScenario) -> TransitionState:
    """Initial state for the current transition scenario."""
    return transition_scenario.initial_state


@pytest.fixture
def transition_inputs(transition_scenario: TransitionScenario) -> tuple[Any, ...]:
    """Input sequence for the current transition scenario."""
    return transition_scenario.inputs


@pytest.fixture
def expected_state(transition_scenario: TransitionScenario) -> TransitionState:
    """Expected final state for the current transition scenario."""
    return transition_scenario.expected_state


@pytest.fixture
def expected_counter(transition_scenario: TransitionScenario) -> int:
    """Expected final counter value for the current transition scenario."""
    return transition_scenario.expected_counter


@pytest.fixture
def batch_config(transition_scenario: TransitionScenario) -> BatchConfig | None:
    """Batch configuration for the current transition scenario, if any."""
    return transition_scenario.batch_config


@pytest.fixture
def expect_error(transition_scenario: TransitionScenario) -> bool:
    """Whether the current scenario is expected to raise an exception."""
    return transition_scenario.expect_error


@pytest.fixture
def expected_error_type(
    transition_scenario: TransitionScenario,
) -> type[BaseException] | None:
    """Expected exception type when ``expect_error`` is True."""
    return transition_scenario.error_type


# ---------------------------------------------------------------------------
# Manager factory fixture (wire this to the real implementation)
# ---------------------------------------------------------------------------

class _PlaceholderStateTransitionManager:
    """Stand-in manager used until the real implementation is available.

    The fixture scaffold intentionally does not depend on a concrete class.
    Replace ``_PlaceholderStateTransitionManager`` with the real
    ``StateTransitionManager`` import and construction in the fixture below.
    """

    def __init__(self, initial_state: TransitionState = TransitionState.IDLE) -> None:
        self.state = initial_state
        self.counter = 0
        self._threshold = 3

    def set_threshold(self, threshold: int) -> None:
        """Configure the transition threshold."""
        self._threshold = threshold

    def process(self, value: Any) -> TransitionState:
        """Process a single input and update internal state.

        This placeholder logic is only sufficient to exercise the fixture
        scaffolding. Replace with real semantics once the manager exists.
        """
        if value == "__reset__":
            self.counter = 0
            self.state = TransitionState.IDLE
            return self.state

        if isinstance(value, float) and value != value:  # NaN check
            self.state = TransitionState.ERROR
            raise ValueError("NaN input is not allowed")

        if not isinstance(value, int):
            return self.state

        self.counter += value
        if self.counter < 0:
            self.counter = 0
            self.state = TransitionState.RECOVERING
        elif self.counter >= self._threshold:
            self.state = TransitionState.THRESHOLD_REACHED
        else:
            self.state = TransitionState.COUNTING

        return self.state


@pytest.fixture
def state_transition_manager(initial_state: TransitionState) -> Any:
    """Return a configured ``StateTransitionManager`` instance for the test.

    TODO: Replace ``_PlaceholderStateTransitionManager`` with the real import
    once ``StateTransitionManager`` is implemented, e.g.::

        from perpetua.state_transition import StateTransitionManager
        return StateTransitionManager(initial_state=initial_state.value)
    """
    return _PlaceholderStateTransitionManager(initial_state=initial_state)
