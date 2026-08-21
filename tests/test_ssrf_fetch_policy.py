"""Tests for the Layer-1 arbitrary-fetch SSRF policy."""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from utils.ssrf_fetch_policy import (
    SSRFPolicyError,
    _is_denied_ip,
    validate_fetch_url,
)

pytestmark = pytest.mark.unit


# --- Unit: known-good and known-bad cases -----------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "https://api.perplexity.ai/v1/search",
        "http://api.x.ai/v1/chat",
        "https://openrouter.ai/api/v1/models",
        "https://api.anthropic.com/v1/messages",
    ],
)
def test_allows_vendor_allowlisted_hosts(url: str) -> None:
    assert validate_fetch_url(url) == url


def test_non_allowlisted_hostname_fails_closed_by_design() -> None:
    # Not an IP literal, not vendor-allowlisted -- this module cannot resolve
    # DNS, so it must fail closed rather than silently allow it (see module
    # docstring). Callers needing arbitrary public hostnames must go through
    # the Layer-2 pinning transport.
    with pytest.raises(SSRFPolicyError):
        validate_fetch_url("https://example.com/path?q=1")


@pytest.mark.parametrize(
    "url,reason",
    [
        ("http://169.254.169.254/latest/meta-data/", "link-local IMDS"),
        ("http://169.254.170.2/v2/credentials", "ECS task metadata"),
        ("http://[fd00:ec2::254]/", "AWS IMDS IPv6"),
        ("http://100.64.0.1/", "CGNAT"),
        ("http://224.0.0.1/", "IPv4 multicast"),
        ("http://[ff02::1]/", "IPv6 multicast"),
        ("http://[::ffff:169.254.169.254]/", "IPv4-mapped IPv6 IMDS"),
        ("http://127.0.0.1/", "loopback"),
        ("http://192.168.1.1/", "RFC1918"),
        ("http://0.0.0.0/", "unspecified"),
        ("ftp://example.com/", "disallowed scheme"),
        ("http://user:pass@example.com/", "credentials in URL"),
        ("http://example.com/\r\nHost: evil", "CRLF injection"),
        ("http://internal-host/", "unresolved hostname fails closed"),
    ],
)
def test_denies_dangerous_targets(url: str, reason: str) -> None:
    with pytest.raises(SSRFPolicyError):
        validate_fetch_url(url)


def test_empty_url_denied() -> None:
    with pytest.raises(SSRFPolicyError):
        validate_fetch_url("")


def test_allow_private_override_permits_private_ip() -> None:
    assert validate_fetch_url("http://192.168.1.1/", allow_private=True) == (
        "http://192.168.1.1/"
    )


def test_allow_private_override_does_not_bypass_scheme_or_userinfo() -> None:
    with pytest.raises(SSRFPolicyError):
        validate_fetch_url("ftp://192.168.1.1/", allow_private=True)
    with pytest.raises(SSRFPolicyError):
        validate_fetch_url("http://user:pass@192.168.1.1/", allow_private=True)


# --- Property: every reserved/private/special IPv4 octet/hex/mixed encoding -

_DENIED_IPV4_NETWORKS = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "100.64.0.0/10",
    "224.0.0.0/4",
    "0.0.0.0/8",
]


@given(
    network=st.sampled_from(_DENIED_IPV4_NETWORKS),
    offset=st.integers(min_value=0, max_value=2**16 - 1),
)
def test_property_denied_ipv4_ranges_always_denied(network: str, offset: int) -> None:
    import ipaddress

    net = ipaddress.ip_network(network)
    addr = ipaddress.ip_address(int(net.network_address) + (offset % net.num_addresses))
    assert _is_denied_ip(addr) is True


@given(st.integers(min_value=0, max_value=2**32 - 1))
def test_property_public_ipv4_never_false_denied_unless_reserved(raw: int) -> None:
    import ipaddress

    addr = ipaddress.ip_address(raw)
    # Ground truth: an address must be denied iff it is NOT globally routable
    # unicast, OR it is multicast. Python's ipaddress.is_global reports every
    # multicast address (including the 224.0.0.0/4 network base itself) as
    # globally routable -- confirmed directly: 224.0.0.0/224.0.0.1/
    # 239.255.255.255/232.0.0.0 are all is_global=True in this stdlib version
    # -- so is_global alone is not a correct oracle for this policy, which
    # must always deny multicast regardless of that stdlib classification.
    assert _is_denied_ip(addr) == (not addr.is_global or addr.is_multicast)
