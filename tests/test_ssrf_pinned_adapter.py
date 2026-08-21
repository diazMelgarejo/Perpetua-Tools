"""Unit tests for SSRFPinnedHTTPAdapter. No live network, no IMDS traffic."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from utils.ssrf_pinned_adapter import (
    AddressDenied,
    RedirectDenied,
    SSRFPolicyError,
    default_address_allowed,
    default_url_allowed,
    ssrf_request,
    validate_resolved,
)


@pytest.mark.parametrize(
    "raw",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.1",
        "169.254.169.254",
        "169.254.170.2",
        "100.64.0.1",
        "224.0.0.1",
        "0.0.0.0",
        "::1",
        "::ffff:169.254.169.254",
        "fd00:ec2::254",
        "fe80::1",
    ],
)
def test_denied_addresses(raw: str) -> None:
    with pytest.raises(AddressDenied):
        default_address_allowed(raw)


def test_public_address_ok() -> None:
    default_address_allowed("1.1.1.1")


def test_url_rejects_userinfo_and_scheme() -> None:
    with pytest.raises(SSRFPolicyError):
        default_url_allowed("http://user:pass@example.com/")
    with pytest.raises(SSRFPolicyError):
        default_url_allowed("file:///etc/passwd")
    with pytest.raises(SSRFPolicyError):
        default_url_allowed("https://example.com/\r\nHost: 169.254.169.254")


def test_mixed_public_private_aaaa_fails() -> None:
    infos = [
        (0, 0, 0, "", ("1.1.1.1", 443)),
        (0, 0, 0, "", ("169.254.169.254", 443)),
    ]
    with patch("utils.ssrf_pinned_adapter.socket.getaddrinfo", return_value=infos):
        with pytest.raises(AddressDenied):
            validate_resolved("evil.example", 443, default_address_allowed)


def test_ssrf_request_refuses_redirect_to_metadata() -> None:
    class _FakeResp:
        status_code = 302
        is_redirect = True
        headers = {"Location": "http://169.254.169.254/latest/meta-data/"}

    class _FakeSess:
        def request(self, *args, **kwargs):
            return _FakeResp()

        def close(self) -> None:
            return None

    with pytest.raises((AddressDenied, RedirectDenied, SSRFPolicyError)):
        ssrf_request(
            "GET",
            "https://example.com/out",
            session=_FakeSess(),  # type: ignore[arg-type]
            allow_redirects=True,
        )


def test_hook_endpoint_policy() -> None:
    from utils.ssrf_pinned_adapter import hook_endpoint_policy

    addr_checker, url_checker = hook_endpoint_policy()
    assert callable(addr_checker)
    assert callable(url_checker)
    # Valid address passes
    addr_checker("1.1.1.1")
    # Denied address fails
    with pytest.raises((AddressDenied, Exception)):
        addr_checker("127.0.0.1")

