"""SSRF-safe requests adapter: resolve once, pin IP, control redirects.

Layer 2 companion to ``endpoint_policy_core`` (Layer 1 pre-flight).
This module does not claim to replace egress/IMDS controls.

Drop-in path for Perpetua-Tools:
    src/utils/ssrf_pinned_adapter.py

Usage::

    from utils.ssrf_pinned_adapter import ssrf_request, ssrf_session

    r = ssrf_request("GET", url, timeout=10)
    # or
    with ssrf_session() as s:
        r = s.get(url, timeout=10)  # redirects are refused; use ssrf_request to hop
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Sequence
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.poolmanager import PoolManager
from urllib3.util.connection import allowed_gai_family

try:
    from urllib3.util.ssl_ import create_urllib3_context
except ImportError:  # pragma: no cover
    from urllib3.util.ssl_ import create_urllib3_context  # type: ignore[attr-defined]

# Layer-1's _is_denied_ip is the SSOT deny predicate (src/utils/ssrf_fetch_policy.py,
# 22 tests incl. hypothesis property tests). Import it when available and prefer it;
# _DENIED_NETWORKS below stays only as this module's standalone fallback for contexts
# where Layer-1 isn't importable (e.g. this adapter dropped into a repo without it) --
# mirrors this codebase's own dual-try import-resolution convention.
try:
    from src.utils.ssrf_fetch_policy import _is_denied_ip as _layer1_is_denied_ip
except ImportError:
    try:
        from utils.ssrf_fetch_policy import _is_denied_ip as _layer1_is_denied_ip
    except ImportError:
        _layer1_is_denied_ip = None


MAX_REDIRECTS_DEFAULT = 3
ALLOWED_SCHEMES = frozenset({"http", "https"})

_DENIED_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
    ipaddress.ip_network("fd00:ec2::254/128"),
)


class AddressDenied(requests.RequestException):
    """Destination resolved to a blocked address. Fail closed."""


class RedirectDenied(requests.RequestException):
    """Automatic or unsafe redirect refused."""


class SSRFPolicyError(requests.RequestException):
    """URL failed structural policy (scheme, userinfo, control chars)."""


def _normalize_ip(raw: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    addr = ipaddress.ip_address(raw)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    return addr


def default_address_allowed(raw: str) -> None:
    """Deny reserved, private, link-local, CGNAT, multicast, and IMDS ranges.

    Delegates to Layer-1's ``_is_denied_ip`` when importable (the SSOT deny
    predicate, see the import block above); falls back to this module's own
    ``_DENIED_NETWORKS`` + ``is_global`` check only when Layer-1 isn't
    available, so the two lists can't silently drift out of sync in the
    common case.
    """
    try:
        addr = _normalize_ip(raw)
    except ValueError as exc:
        raise AddressDenied(f"unparseable address: {raw!r}") from exc
    if _layer1_is_denied_ip is not None:
        if _layer1_is_denied_ip(addr):
            raise AddressDenied(f"blocked address: {addr}")
        return
    if not addr.is_global or any(addr in net for net in _DENIED_NETWORKS):
        raise AddressDenied(f"blocked address: {addr}")


def default_url_allowed(url: str) -> None:
    if any(ch in url for ch in ("\r", "\n", "\x00")):
        raise SSRFPolicyError("control characters in URL")
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise SSRFPolicyError(f"scheme not allowed: {parsed.scheme!r}")
    if parsed.username is not None or parsed.password is not None:
        raise SSRFPolicyError("userinfo is not allowed")
    if not parsed.hostname:
        raise SSRFPolicyError("URL has no hostname")


def resolve_all(hostname: str, port: int) -> list[str]:
    """Return every A/AAAA literal. Empty or error → fail closed."""
    family = allowed_gai_family()
    try:
        infos = socket.getaddrinfo(hostname, port, family, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AddressDenied(f"DNS failed for {hostname!r}: {exc}") from exc
    seen: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip = sockaddr[0]
        if ip not in seen:
            seen.append(ip)
    if not seen:
        raise AddressDenied(f"no addresses for {hostname!r}")
    return seen


def validate_resolved(hostname: str, port: int, checker: Callable[[str], None]) -> list[str]:
    ips = resolve_all(hostname, port)
    for ip in ips:
        checker(ip)
    return ips


def _host_header(hostname: str, port: int, scheme: str) -> str:
    default = 443 if scheme == "https" else 80
    if ":" in hostname and not hostname.startswith("["):
        host = f"[{hostname}]"
    else:
        host = hostname
    if port == default:
        return host
    return f"{host}:{port}"


class _PinnedHTTPConnection(HTTPConnection):
    def __init__(
        self,
        *args: Any,
        pinned_ip: str | None = None,
        address_checker: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._pinned_ip = pinned_ip
        self._address_checker = address_checker or default_address_allowed

    def _new_conn(self) -> socket.socket:
        if not self._pinned_ip:
            raise AddressDenied("connection missing pinned IP")
        extra: dict[str, Any] = {}
        if self.source_address:
            extra["source_address"] = self.source_address
        if self.socket_options:
            extra["socket_options"] = self.socket_options
        sock = socket.create_connection(
            (self._pinned_ip, self.port),
            self.timeout,
            **extra,
        )
        peer = sock.getpeername()[0]
        self._address_checker(peer)
        return sock


class _PinnedHTTPSConnection(HTTPSConnection):
    def __init__(
        self,
        *args: Any,
        pinned_ip: str | None = None,
        sni_hostname: str | None = None,
        address_checker: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._pinned_ip = pinned_ip
        self._address_checker = address_checker or default_address_allowed
        if sni_hostname:
            self.server_hostname = sni_hostname
            self.assert_hostname = sni_hostname

    def _new_conn(self) -> socket.socket:
        if not self._pinned_ip:
            raise AddressDenied("connection missing pinned IP")
        extra: dict[str, Any] = {}
        if self.source_address:
            extra["source_address"] = self.source_address
        if self.socket_options:
            extra["socket_options"] = self.socket_options
        sock = socket.create_connection(
            (self._pinned_ip, self.port),
            self.timeout,
            **extra,
        )
        peer = sock.getpeername()[0]
        self._address_checker(peer)
        return sock


class _PinnedHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _PinnedHTTPConnection

    def __init__(
        self,
        *args: Any,
        pinned_ip: str | None = None,
        address_checker: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        self.pinned_ip = pinned_ip
        self.address_checker = address_checker
        super().__init__(*args, **kwargs)

    def _new_conn(self) -> HTTPConnection:
        self.conn_kw = dict(self.conn_kw)
        self.conn_kw["pinned_ip"] = self.pinned_ip
        self.conn_kw["address_checker"] = self.address_checker
        return super()._new_conn()


class _PinnedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _PinnedHTTPSConnection

    def __init__(
        self,
        *args: Any,
        pinned_ip: str | None = None,
        sni_hostname: str | None = None,
        address_checker: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        self.pinned_ip = pinned_ip
        self.address_checker = address_checker
        if sni_hostname:
            kwargs.setdefault("assert_hostname", sni_hostname)
            kwargs.setdefault("server_hostname", sni_hostname)
        super().__init__(*args, **kwargs)
        self.sni_hostname = sni_hostname

    def _new_conn(self) -> HTTPSConnection:
        self.conn_kw = dict(self.conn_kw)
        self.conn_kw["pinned_ip"] = self.pinned_ip
        self.conn_kw["sni_hostname"] = self.sni_hostname
        self.conn_kw["address_checker"] = self.address_checker
        return super()._new_conn()


# Fields this module injects into connection_pool_kw that urllib3's PoolKey
# namedtuple has no field for. Passing them straight into
# urllib3.poolmanager._default_key_normalizer() raises
# "PoolKey.__new__() got an unexpected keyword argument" -- reproducible
# with zero mocking, on ANY real connection_from_host() call, confirmed to
# predate this session's changes (present since the adapter's very first
# commit). PoolKey already has fields for assert_hostname/server_hostname;
# only these four are genuinely foreign to it.
_NON_POOL_KEY_FIELDS = frozenset({"pinned_ip", "address_checker", "assert_same_host", "sni_hostname"})


def _pinned_pool_key_normalizer(request_context: dict[str, Any]) -> "PoolKey":
    """Build a PoolKey, excluding fields PoolKey doesn't know about.

    ``key_fn_by_scheme`` is urllib3's own documented extension point for
    this exact situation (see ``_default_key_normalizer``'s docstring:
    "provide alternate callables to key_fn_by_scheme"). The excluded
    fields still reach the pool's own ``__init__`` normally -- this only
    changes what's used to compute the connection-pool cache key, not what
    the pool is constructed with (``connection_from_pool_key`` re-uses the
    original, unfiltered ``request_context`` for that).
    """
    from urllib3.poolmanager import PoolKey, _default_key_normalizer

    filtered = {k: v for k, v in request_context.items() if k not in _NON_POOL_KEY_FIELDS}
    return _default_key_normalizer(PoolKey, filtered)


class _PinnedPoolManager(PoolManager):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pool_classes_by_scheme = {
            "http": _PinnedHTTPConnectionPool,
            "https": _PinnedHTTPSConnectionPool,
        }
        self.key_fn_by_scheme = {
            "http": _pinned_pool_key_normalizer,
            "https": _pinned_pool_key_normalizer,
        }


class SSRFPinnedHTTPAdapter(HTTPAdapter):
    """requests adapter: validate every resolved IP, connect to one pinned IP.

    Automatic redirects are rejected in ``send``. Use :func:`ssrf_request`
    to follow Location hops with re-validation.
    """

    def __init__(
        self,
        *args: Any,
        address_checker: Callable[[str], None] | None = None,
        url_checker: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        self.address_checker = address_checker or default_address_allowed
        self.url_checker = url_checker or default_url_allowed
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: Any) -> None:
        context = pool_kwargs.pop("ssl_context", None) or create_urllib3_context()
        self.poolmanager = _PinnedPoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=context,
            **pool_kwargs,
        )

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: Any = None,
        verify: Any = True,
        cert: Any = None,
        proxies: Any = None,
    ) -> requests.Response:
        if proxies:
            raise SSRFPolicyError("proxies are not supported on the pinned adapter")
        url = request.url or ""
        self.url_checker(url)
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        scheme = parsed.scheme
        port = parsed.port or (443 if scheme == "https" else 80)
        ips = validate_resolved(hostname, port, self.address_checker)
        pinned = ips[0]
        request.headers["Host"] = _host_header(hostname, port, scheme)

        pool_kwargs: dict[str, Any] = {
            "pinned_ip": pinned,
            "address_checker": self.address_checker,
            "assert_same_host": False,
        }
        if scheme == "https":
            pool_kwargs["sni_hostname"] = hostname
            pool_kwargs["assert_hostname"] = hostname
            pool_kwargs["server_hostname"] = hostname

        self.poolmanager.connection_pool_kw.update(pool_kwargs)
        try:
            return super().send(
                request,
                stream=stream,
                timeout=timeout,
                verify=verify,
                cert=cert,
                proxies=None,
            )
        finally:
            for key in (
                "pinned_ip",
                "address_checker",
                "sni_hostname",
                "assert_hostname",
                "server_hostname",
                "assert_same_host",
            ):
                self.poolmanager.connection_pool_kw.pop(key, None)


def ssrf_session(
    *,
    address_checker: Callable[[str], None] | None = None,
    url_checker: Callable[[str], None] | None = None,
) -> requests.Session:
    session = requests.Session()
    adapter = SSRFPinnedHTTPAdapter(
        address_checker=address_checker,
        url_checker=url_checker,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.max_redirects = 0
    return session


def _require_pinned_adapter(sess: requests.Session, url: str) -> None:
    """Reject sessions that do not route ``url`` through the pinned adapter.

    A caller-supplied ``requests.Session`` without ``SSRFPinnedHTTPAdapter``
    mounted falls back to urllib3's default pool, which re-resolves DNS at
    connect time and skips IP pinning, redirect control, and peer
    validation -- ``check_url`` alone cannot compensate for that gap.
    """
    get_adapter = getattr(sess, "get_adapter", None)
    if not callable(get_adapter):
        raise SSRFPolicyError("session must expose get_adapter() to verify SSRF pinning")
    if not isinstance(get_adapter(url), SSRFPinnedHTTPAdapter):
        raise SSRFPolicyError(f"session adapter for {url!r} is not SSRFPinnedHTTPAdapter")


def ssrf_request(
    method: str,
    url: str,
    *,
    max_redirects: int = MAX_REDIRECTS_DEFAULT,
    allow_redirects: bool = True,
    address_checker: Callable[[str], None] | None = None,
    url_checker: Callable[[str], None] | None = None,
    session: requests.Session | None = None,
    **kwargs: Any,
) -> requests.Response:
    """Issue a request with IP pinning. Follow redirects only after re-validation.

    ``allow_redirects`` on the underlying session is forced off. This function
    implements hops itself so each Location is parsed, resolved, and checked.
    """
    own_session = session is None
    sess = session or ssrf_session(
        address_checker=address_checker,
        url_checker=url_checker,
    )
    # ssrf_session()'s max_redirects=0 is for its own direct-usage contract
    # ("redirects are refused", per its docstring) -- but that same setting
    # makes requests.Session.send()'s internal precomputation of `r._next`
    # (resolve_redirects(..., yield_requests=True)) raise TooManyRedirects
    # on literally the first redirect response, regardless of the
    # allow_redirects=False passed to every .request() call below, before
    # this function's own hop loop and its per-hop check_url/
    # validate_resolved re-validation ever runs. That precomputation is a
    # single, local `next()` call (yields once, never sends) -- raising the
    # ceiling here does not reopen any auto-follow risk; this loop still
    # tracks and enforces its own hop count independently via `hops`/
    # `max_redirects` below.
    sess.max_redirects = max(max_redirects, 1)
    check_url = url_checker or default_url_allowed
    hops = 0
    current = url
    try:
        while True:
            check_url(current)
            _require_pinned_adapter(sess, current)
            kwargs = dict(kwargs)
            kwargs["allow_redirects"] = False
            response = sess.request(method, current, **kwargs)
            if not allow_redirects or response.is_redirect is False:
                return response
            if hops >= max_redirects:
                raise RedirectDenied(f"redirect limit {max_redirects} exceeded")
            location = response.headers.get("Location")
            if not location:
                raise RedirectDenied("redirect without Location")
            nxt = urljoin(current, location)
            check_url(nxt)
            # RFC 9110 §15.4: 301/302/303 may convert the method to GET, and
            # in that case the original body is meaningless and must be
            # dropped. 307/308 explicitly preserve both the method and the
            # request body on the redirected request -- do not strip data/
            # json/files for those, or a legitimate POST-preserving redirect
            # silently becomes a bodyless request.
            if response.status_code in (301, 302, 303):
                method = "GET"
                kwargs.pop("data", None)
                kwargs.pop("json", None)
                kwargs.pop("files", None)
            current = nxt
            hops += 1
    finally:
        if own_session:
            sess.close()


def hook_endpoint_policy() -> tuple[Callable[[str], None], Callable[[str], None]]:
    """Prefer Perpetua-Tools Layer 1 checkers when importable."""
    try:
        from src.utils.ssrf_fetch_policy import (
            assert_address_allowed,
            assert_url_allowed,
        )
        return assert_address_allowed, assert_url_allowed
    except ImportError:
        try:
            from utils.ssrf_fetch_policy import (
                assert_address_allowed,
                assert_url_allowed,
            )
            return assert_address_allowed, assert_url_allowed
        except ImportError:
            pass

    try:
        from src.utils.endpoint_policy_core import (
            assert_address_allowed,
            assert_url_allowed,
        )
        return assert_address_allowed, assert_url_allowed
    except ImportError:
        try:
            from utils.endpoint_policy_core import (
                assert_address_allowed,
                assert_url_allowed,
            )
            return assert_address_allowed, assert_url_allowed
        except ImportError:
            pass
            
    return default_address_allowed, default_url_allowed
