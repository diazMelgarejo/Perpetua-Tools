"""Fallback run ids for harness episodic records must not expose process ids."""
import importlib.util
import os
import re
import sys
import types
import uuid
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".agent/harness/hooks/_provenance.py"


@pytest.fixture
def provenance(monkeypatch):
    """Load a fresh copy of the provenance hook with ``AGENT_RUN_ID`` unset."""
    monkeypatch.delenv("AGENT_RUN_ID", raising=False)
    spec = importlib.util.spec_from_file_location("harness_provenance_under_test", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fallback_run_id_is_the_uuid_prefix_and_never_reads_the_pid(provenance, monkeypatch):
    """The fallback is the first 12 hex digits of a UUID and never touches the pid."""
    # Arrange: a fixed UUID, so the expected id is exact rather than probabilistic. Both
    # collaborators are replaced on the module under test only, not on the shared stdlib modules.
    fixed = uuid.UUID("0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(provenance, "uuid", types.SimpleNamespace(uuid4=lambda: fixed))

    class NoPidOs:
        """Delegate to the real ``os`` module but fail if the process id is requested."""

        def __getattr__(self, name):
            """Return the real ``os`` attribute for everything except ``getpid``."""
            if name == "getpid":
                raise AssertionError("fallback run id must not derive from the process id")
            return getattr(os, name)

    monkeypatch.setattr(provenance, "os", NoPidOs())

    # Act
    run_id = provenance.run_id()

    # Assert
    assert run_id == "run-0123456789ab"
    assert re.fullmatch(r"run-[0-9a-f]{12}", run_id)


def test_fallback_run_id_is_stable_within_a_process(provenance):
    """Repeated calls return the same fallback id for the life of the process."""
    assert provenance.run_id() == provenance.run_id()


def test_explicit_agent_run_id_is_honoured(provenance, monkeypatch):
    """A configured ``AGENT_RUN_ID`` wins over the generated fallback."""
    monkeypatch.setenv("AGENT_RUN_ID", "ci-run-7")

    assert provenance.run_id() == "ci-run-7"


@pytest.mark.parametrize("configured", ["", "   ", "\t\n"])
def test_blank_agent_run_id_falls_back_to_an_opaque_id(provenance, monkeypatch, configured):
    """An empty or whitespace-only ``AGENT_RUN_ID`` is treated as unset."""
    monkeypatch.setenv("AGENT_RUN_ID", configured)

    assert re.fullmatch(r"run-[0-9a-f]{12}", provenance.run_id())


def test_agent_run_id_is_stripped(provenance, monkeypatch):
    """Surrounding whitespace is not part of a configured run id."""
    monkeypatch.setenv("AGENT_RUN_ID", "  ci-run-7\n")

    assert provenance.run_id() == "ci-run-7"
