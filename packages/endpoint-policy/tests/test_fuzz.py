"""Randomized boundary-safety fuzz: only ModelEndpointPolicyError may escape.

Hand-rolled random loops (no hypothesis dependency), mirroring orama-system
tests/test_endpoint_policy_fuzz.py idiom.
"""
from __future__ import annotations

import random
import string
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from endpoint_policy import ModelEndpointPolicyError, validate_model_endpoint_url  # noqa: E402

_CHARS = string.ascii_letters + string.digits + ":/[]@%.-_ "


def _rand() -> str:
    rng = random.Random()
    return "".join(rng.choice(_CHARS) for _ in range(rng.randint(0, 60)))


@pytest.mark.parametrize("_", range(300))
def test_no_crash_on_random_input(_):
    s = _rand()
    try:
        validate_model_endpoint_url(s, allow_public=False)
    except ModelEndpointPolicyError:
        pass
    except Exception as exc:
        raise AssertionError(f"unexpected exception leaked for {s!r}: {type(exc)}") from exc


@pytest.mark.parametrize("port", [-1, 0, 65535, 65536, 99999, 10**12])
def test_port_boundaries_never_leak_valueerror(port):
    try:
        validate_model_endpoint_url(f"http://localhost:{port}")
    except ModelEndpointPolicyError:
        pass
