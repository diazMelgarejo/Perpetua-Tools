"""Policy tests for utils.model_endpoint_url (Security Fix 5)."""
from __future__ import annotations

import pytest

from utils.model_endpoint_url import (
    ModelEndpointPolicyError,
    allow_public_model_endpoints,
    parse_model_endpoint_list,
    redact_endpoint_for_log,
    validate_model_endpoint_url,
)


@pytest.fixture(autouse=True)
def _clear_public_opt_in(monkeypatch):
    monkeypatch.delenv("ALLOW_PUBLIC_MODEL_ENDPOINTS", raising=False)


class TestLoopbackAndPrivate:
    def test_localhost_allowed(self):
        assert validate_model_endpoint_url("http://localhost:1234") == "http://localhost:1234"

    def test_127_allowed(self):
        assert validate_model_endpoint_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434"

    def test_bare_host_port_canonicalized(self):
        assert validate_model_endpoint_url("localhost:1234") == "http://localhost:1234"
        assert validate_model_endpoint_url("127.0.3.2:11434") == "http://127.0.3.2:11434"

    def test_rfc1918_192_allowed(self):
        url = validate_model_endpoint_url("http://192.168.1.1:1234")
        assert url == "http://192.168.1.1:1234"

    def test_rfc1918_10_allowed(self):
        assert validate_model_endpoint_url("http://10.0.0.1:1234") == "http://10.0.0.1:1234"

    def test_rfc1918_172_allowed(self):
        assert validate_model_endpoint_url("http://172.16.0.1:1234") == "http://172.16.0.1:1234"

    def test_parse_comma_list(self):
        raw = "http://127.0.3.1:1234, http://127.0.0.1:1234"
        assert parse_model_endpoint_list(raw) == [
            "http://127.0.3.1:1234",
            "http://127.0.0.1:1234",
        ]


class TestPublicBlocked:
    def test_link_local_metadata_blocked(self):
        with pytest.raises(ModelEndpointPolicyError, match="RFC1918"):
            validate_model_endpoint_url("http://169.254.169.254")

    def test_ipv4_mapped_link_local_metadata_blocked(self):
        with pytest.raises(ModelEndpointPolicyError, match="RFC1918"):
            validate_model_endpoint_url("http://[::ffff:169.254.169.254]:80")

    def test_public_ip_blocked(self):
        with pytest.raises(ModelEndpointPolicyError, match="RFC1918"):
            validate_model_endpoint_url("http://8.8.8.8:1234")

    def test_public_hostname_blocked(self):
        with pytest.raises(ModelEndpointPolicyError):
            validate_model_endpoint_url("http://evil.example.com:1234")

    def test_127_prefix_hostname_not_treated_as_loopback(self):
        with pytest.raises(ModelEndpointPolicyError, match="RFC1918"):
            validate_model_endpoint_url("http://127.attacker.example:8000")

    def test_127_prefix_hostname_blocked_with_require_tls_flag(self):
        with pytest.raises(ModelEndpointPolicyError, match="RFC1918"):
            validate_model_endpoint_url(
                "http://127.attacker.example:8000",
                require_tls_for_non_loopback=True,
            )

    def test_public_ip_allowed_with_opt_in(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PUBLIC_MODEL_ENDPOINTS", "1")
        assert allow_public_model_endpoints()
        assert validate_model_endpoint_url("http://8.8.8.8:1234") == "http://8.8.8.8:1234"

    def test_public_hostname_allowed_with_opt_in(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PUBLIC_MODEL_ENDPOINTS", "true")
        assert validate_model_endpoint_url("http://lm.example.com:1234") == (
            "http://lm.example.com:1234"
        )


class TestMalformed:
    def test_file_scheme_rejected(self):
        with pytest.raises(ModelEndpointPolicyError, match="scheme"):
            validate_model_endpoint_url("file:///etc/passwd")

    def test_credentials_rejected(self):
        with pytest.raises(ModelEndpointPolicyError, match="credentials"):
            validate_model_endpoint_url("http://user:pass@127.0.3.1:1234")

    def test_empty_rejected(self):
        with pytest.raises(ModelEndpointPolicyError, match="empty"):
            validate_model_endpoint_url("   ")

    def test_malformed_port_rejected_as_policy_error(self):
        with pytest.raises(ModelEndpointPolicyError, match="invalid endpoint URL"):
            validate_model_endpoint_url("http://127.0.0.1:notaport")

    def test_out_of_range_port_rejected_as_policy_error(self):
        with pytest.raises(ModelEndpointPolicyError, match="invalid endpoint URL"):
            validate_model_endpoint_url("http://127.0.0.1:99999")

    def test_parse_list_skip_invalid_handles_malformed_port(self):
        raw = "http://127.0.0.1:11434, http://127.0.0.1:notaport"
        assert parse_model_endpoint_list(raw, skip_invalid=True) == [
            "http://127.0.0.1:11434",
        ]


class TestRequireTlsForNonLoopback:
    """Opt-in scheme hardening for trusted, credential-bearing callers.

    Reproduces CodeRabbit review 5234774766 (orama-system PR#363), Finding 2:
    a trusted control-plane client (PT pipeline route) sends a bearer token
    on every call; plain HTTP to a private-network (non-loopback) endpoint
    exposes that token to anyone on-path on the LAN segment. Default
    behavior (flag unset/False) is unchanged -- every other caller of this
    function (LM Studio / Ollama / Windows-coder-pool endpoints, explicitly
    documented as trusted-LAN HTTP by design) is unaffected.
    """

    def test_default_still_allows_http_to_private_network_host(self):
        # Sweeping this module's default would break the documented
        # LAN-trusting model-inference use case; the flag must be opt-in.
        assert (
            validate_model_endpoint_url("http://192.168.1.50:8000")
            == "http://192.168.1.50:8000"
        )

    def test_flag_allows_the_documented_loopback_default(self):
        assert (
            validate_model_endpoint_url(
                "http://localhost:8000", require_tls_for_non_loopback=True
            )
            == "http://localhost:8000"
        )
        assert (
            validate_model_endpoint_url(
                "http://127.0.0.1:8000", require_tls_for_non_loopback=True
            )
            == "http://127.0.0.1:8000"
        )

    def test_flag_rejects_http_to_rfc1918_private_host(self):
        with pytest.raises(ModelEndpointPolicyError, match="https"):
            validate_model_endpoint_url(
                "http://192.168.1.50:8000", require_tls_for_non_loopback=True
            )

    def test_flag_rejects_http_to_10_range_private_host(self):
        with pytest.raises(ModelEndpointPolicyError, match="https"):
            validate_model_endpoint_url(
                "http://10.0.0.5:8000", require_tls_for_non_loopback=True
            )

    def test_flag_allows_https_to_private_network_host(self):
        assert (
            validate_model_endpoint_url(
                "https://192.168.1.50:8443", require_tls_for_non_loopback=True
            )
            == "https://192.168.1.50:8443"
        )


class TestLoggingRedaction:
    def test_private_ip_redacted(self):
        out = redact_endpoint_for_log("http://127.0.4.1:1234")
        assert "127.0.4.1" not in out
        assert "127.0.4.*" in out

    def test_localhost_not_redacted(self):
        assert "localhost" in redact_endpoint_for_log("http://localhost:1234")
