"""Contract tests for shared endpoint transport identity policy."""
from __future__ import annotations

from utils.endpoint_policy_core import (
    TransportIdentity,
    build_transport_url,
    parse_transport_identity,
)


def test_parse_transport_identity_preserves_scheme_host_and_port():
    identity = parse_transport_identity("https://win-box.example:1234")

    assert identity == TransportIdentity(
        scheme="https",
        hostname="win-box.example",
        port=1234,
    )


def test_build_transport_url_replaces_only_backend_port():
    assert build_transport_url("https://win-box.example:1234", 11434) == (
        "https://win-box.example:11434"
    )


def test_build_transport_url_defaults_bare_host_to_http():
    assert build_transport_url("192.168.254.108:1234", 11434) == (
        "http://192.168.254.108:11434"
    )


def test_build_transport_url_never_duplicates_scheme():
    result = build_transport_url("http://192.168.254.108:1234", 11434)
    assert result == "http://192.168.254.108:11434"
    assert "http://http" not in result


def test_build_transport_url_rejects_credentials():
    assert build_transport_url("http://user:pass@192.168.254.108:1234", 11434) is None


def test_build_transport_url_rejects_unknown_scheme():
    assert build_transport_url("file:///etc/passwd", 11434) is None


def test_build_transport_url_rejects_malformed_port():
    assert build_transport_url("http://192.168.254.108:notaport", 11434) is None


def test_build_transport_url_reconstructs_ipv6_with_brackets():
    assert build_transport_url("http://[::1]:1234", 11434) == "http://[::1]:11434"
