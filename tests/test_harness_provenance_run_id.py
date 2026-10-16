"""Fallback run ids for harness episodic records must not expose process ids."""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".agent/harness/hooks/_provenance.py"


@pytest.fixture
def provenance(monkeypatch):
    monkeypatch.delenv("AGENT_RUN_ID", raising=False)
    spec = importlib.util.spec_from_file_location("harness_provenance_under_test", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fallback_run_id_is_opaque_and_contains_no_process_id(provenance):
    # Arrange
    run_id = provenance.run_id()

    # Assert
    assert re.fullmatch(r"run-[0-9a-f]{12}", run_id)
    assert str(provenance.os.getpid()) not in run_id


def test_fallback_run_id_is_stable_within_a_process(provenance):
    assert provenance.run_id() == provenance.run_id()


def test_explicit_agent_run_id_is_honoured(provenance, monkeypatch):
    monkeypatch.setenv("AGENT_RUN_ID", "ci-run-7")
    provenance._CACHED_RUN_ID = None

    assert provenance.run_id() == "ci-run-7"
