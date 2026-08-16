"""Contract tests for shared endpoint transport identity policy."""
from __future__ import annotations

import pytest

from utils.endpoint_policy_core import (
    TransportIdentity,
    build_transport_url,
    parse_transport_identity,
)

pytestmark = pytest.mark.unit


def test_parse_transport_identity_preserves_scheme_host_and_port() -> None:
    identity = parse_transport_identity("https://win-box.example:1234")

    assert identity == TransportIdentity(
        scheme="https",
        hostname="win-box.example",
        port=1234,
    )


def test_build_transport_url_replaces_only_backend_port() -> None:
    assert build_transport_url("https://win-box.example:1234", 11434) == (
        "https://win-box.example:11434"
    )


def test_build_transport_url_defaults_bare_host_to_http() -> None:
    assert build_transport_url("127.0.1.1:1234", 11434) == (
        "http://127.0.1.1:11434"
    )


def test_build_transport_url_never_duplicates_scheme() -> None:
    result = build_transport_url("http://127.0.1.1:1234", 11434)
    assert result == "http://127.0.1.1:11434"
    assert "http://http" not in result


def test_build_transport_url_rejects_credentials() -> None:
    assert build_transport_url("http://user:pass@127.0.1.1:1234", 11434) is None


def test_build_transport_url_rejects_unknown_scheme() -> None:
    assert build_transport_url("file:///etc/passwd", 11434) is None


def test_build_transport_url_rejects_malformed_port() -> None:
    assert build_transport_url("http://127.0.1.1:notaport", 11434) is None


def test_build_transport_url_reconstructs_ipv6_with_brackets() -> None:
    assert build_transport_url("http://[::1]:1234", 11434) == "http://[::1]:11434"


def test_build_transport_url_accepts_bare_ipv6() -> None:
    assert build_transport_url("::1", 11434) == "http://[::1]:11434"
