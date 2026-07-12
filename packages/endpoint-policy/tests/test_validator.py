"""Regression vectors + behavior pins for perpetua-endpoint-policy.

Expectations follow THIS validator's egress semantics (loopback/RFC1918
allowed by default — these are local model endpoints), not a public-web SSRF
blocker's inverse stance.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from endpoint_policy import (  # noqa: E402
    ModelEndpointPolicyError,
    parse_model_endpoint_list,
    validate_model_endpoint_url,
)


# ── The six coord-023 regression vectors ─────────────────────────────────────

def test_vector_1_bare_host_localhost_port_canonicalized():
    assert validate_model_endpoint_url("localhost:1234") == "http://localhost:1234"


def test_vector_2_malformed_port_notaport():
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("http://localhost:notaport")


def test_vector_3_out_of_range_port_99999():
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("http://localhost:99999")


def test_vector_4_ssrf_metadata_ip_blocked():
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("http://169.254.169.254")
    # Blocked even with the public opt-in — link-local is never allowed.
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("http://169.254.169.254", allow_public=True)


def test_vector_5_ipv4_mapped_ipv6_bypass_blocked():
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("http://[::ffff:169.254.169.254]")
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("http://[::ffff:169.254.169.254]", allow_public=True)


def test_vector_6_skip_invalid_list_parsing():
    raw = "http://localhost:1234, http://gpu:notaport, http://169.254.169.254, 127.0.2.1:1234"
    ok = parse_model_endpoint_list(raw, allow_public=False, skip_invalid=True)
    assert ok == ["http://localhost:1234", "http://127.0.2.1:1234"]
    with pytest.raises(ModelEndpointPolicyError):
        parse_model_endpoint_list(raw, allow_public=False, skip_invalid=False)


# ── Behavior pins ────────────────────────────────────────────────────────────

def test_ipv4_mapped_loopback_allowed():
    # Mapped loopback classifies as loopback (allowed) after the unwrap.
    assert validate_model_endpoint_url("http://[::ffff:127.0.0.1]:80") == "http://[::ffff:127.0.0.1]:80"


def test_public_host_requires_opt_in():
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("http://api.example.com", allow_public=False)
    assert (
        validate_model_endpoint_url("http://api.example.com", allow_public=True)
        == "http://api.example.com:80"
    )


def test_credentials_rejected():
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("http://user:pass@localhost:1234")


def test_scheme_allowlist():
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("ftp://localhost:1234")
    assert validate_model_endpoint_url("https://localhost") == "https://localhost:443"


def test_empty_rejected():
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("")


def test_env_default_opt_in(monkeypatch):
    monkeypatch.setenv("ALLOW_PUBLIC_MODEL_ENDPOINTS", "1")
    assert validate_model_endpoint_url("http://api.example.com") == "http://api.example.com:80"
    monkeypatch.setenv("ALLOW_PUBLIC_MODEL_ENDPOINTS", "")
    with pytest.raises(ModelEndpointPolicyError):
        validate_model_endpoint_url("http://api.example.com")


# ── Lockstep parity with the live mirror (until publish-time cutover) ────────

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_differential_parity_with_mirror():
    """Package behavior must match src/utils/model_endpoint_url.py accept/reject exactly."""
    sys.path.insert(0, str(_REPO_ROOT / "src"))
    from utils.model_endpoint_url import (
        ModelEndpointPolicyError as MirrorError,
        validate_model_endpoint_url as mirror_validate,
    )

    vectors = [
        "localhost:1234", "http://localhost:notaport", "http://localhost:99999",
        "http://169.254.169.254", "http://[::ffff:169.254.169.254]",
        "http://[::ffff:127.0.0.1]:80", "http://api.example.com",
        "http://user:pass@localhost", "ftp://localhost", "", "127.0.2.1:1234",
        "https://127.0.1.1", "http://gpu-box", "http://localhost:0",
    ]
    for url in vectors:
        try:
            pkg = validate_model_endpoint_url(url, allow_public=False)
        except ModelEndpointPolicyError:
            pkg = "<rejected>"
        try:
            mir = mirror_validate(url, allow_public=False)
        except MirrorError:
            mir = "<rejected>"
        assert pkg == mir, f"parity drift on {url!r}: package={pkg!r} mirror={mir!r}"
