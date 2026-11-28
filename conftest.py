"""Guard for every test directory: no test process may reach a local model engine.

A test that talked to Ollama or LM Studio would load a model on the machine running the suite, with nobody's
approval. The audit hook below cannot be removed or monkeypatched away for the life of the process. Child
processes are covered by the one-model gate itself, which refuses real engines while a test is running.
"""
from __future__ import annotations

import errno
import sys
from contextlib import contextmanager

import pytest

_ENGINE_PORTS = frozenset({11434, 1234})  # Ollama and LM Studio


def _refuse_engine_connections(event: str, args: tuple) -> None:
    if event != "socket.connect":
        return
    address = args[1]
    if isinstance(address, tuple) and len(address) >= 2 and address[1] in _ENGINE_PORTS:
        raise ConnectionRefusedError(errno.ECONNREFUSED, "tests may not reach a local model engine")


sys.addaudithook(_refuse_engine_connections)


@pytest.fixture(autouse=True)
def _call_sites_see_a_gate_that_touches_nothing(monkeypatch):
    """Tests of the gate itself replace ``default_gate`` again with their own fake engines."""
    try:
        from perpetua_tools import local_model_gate
    except ImportError:
        return

    class IdleGate:
        @contextmanager
        def slot(self, engine: str, model: str, url: str, wait: bool = True):
            yield local_model_gate.Decision("already_loaded", "test stub")

    monkeypatch.setattr(local_model_gate, "default_gate", IdleGate)
