"""Unit tests for SSRFPinnedHTTPAdapter. No live network, no IMDS traffic."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from utils.ssrf_pinned_adapter import (
    AddressDenied,
    RedirectDenied,
    SSRFPinnedHTTPAdapter,
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
        "0.0.0.0",  # noqa: S104 -- deny-policy fixture, not a bind address
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
        def __init__(self) -> None:
            self.status_code = 302
            self.is_redirect = True
            self.headers = {"Location": "http://169.254.169.254/latest/meta-data/"}

    class _FakeSess:
        def __init__(self) -> None:
            # ssrf_request now refuses any session that doesn't route through
            # SSRFPinnedHTTPAdapter (see _require_pinned_adapter); satisfy that
            # check so this test still exercises redirect-Location denial,
            # not just the pinning-session guard.
            self._adapter = SSRFPinnedHTTPAdapter()

        def get_adapter(self, url: str):
            return self._adapter

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
    # hook_endpoint_policy() itself tries `src.utils.ssrf_fetch_policy` before
    # falling back to `utils.ssrf_fetch_policy` (see its dual-try resolution).
    # Mirror that exact order here rather than picking one import path
    # ourselves: `src.utils.ssrf_fetch_policy.SSRFPolicyError` and
    # `utils.ssrf_fetch_policy.SSRFPolicyError` are the same class body but
    # DIFFERENT class objects when both module paths are importable in the
    # same interpreter (each import path creates its own module instance) --
    # picking the "wrong" one here made `pytest.raises` fail to match the
    # real exception even though the checker was correctly selected. Whatever
    # hook_endpoint_policy() actually resolved to, this must resolve to the
    # same object.
    try:
        from src.utils.ssrf_fetch_policy import SSRFPolicyError as Layer1SSRFPolicyError
    except ImportError:
        from utils.ssrf_fetch_policy import SSRFPolicyError as Layer1SSRFPolicyError
    from utils.ssrf_pinned_adapter import hook_endpoint_policy

    addr_checker, url_checker = hook_endpoint_policy()
    assert callable(addr_checker)
    assert callable(url_checker)
    # Valid address passes
    addr_checker("1.1.1.1")
    # Denied address fails
    with pytest.raises((AddressDenied, Exception)):
        addr_checker("127.0.0.1")

    # Distinguish the selected policy from the fallback: ssrf_fetch_policy's
    # url_checker has no DNS capability, so it fail-closes on any bare
    # hostname it cannot resolve (unless vendor-allowlisted) -- see
    # utils.ssrf_fetch_policy._host_denied. The Layer-2 fallback
    # (default_url_allowed) has no such check and would let this URL
    # through, since it only validates scheme/userinfo/control-chars. If
    # this raises Layer1SSRFPolicyError, hook_endpoint_policy() really did
    # select the Layer-1 checker, not the fallback.
    with pytest.raises(Layer1SSRFPolicyError):
        url_checker("https://example.com/")


def test_ssrf_request_rejects_session_without_pinned_adapter() -> None:
    """A plain requests.Session bypasses DNS pinning/redirect control entirely --
    ssrf_request must refuse it rather than silently trusting check_url alone."""
    import requests

    with pytest.raises(SSRFPolicyError):
        ssrf_request(
            "GET",
            "https://example.com/out",
            session=requests.Session(),
        )

