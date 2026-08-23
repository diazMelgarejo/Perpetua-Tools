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
import time
from collections.abc import Callable, Sequence
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import requests

from utils.egress_telemetry import EgressEvent, classify_deny_reason, emit
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
    """Split-identity: ``self.host`` (from pool construction) IS the
    validated pin -- the PLACE. TLS/HTTP identity (the NAME, original
    hostname) travels separately via ``server_hostname``/``assert_hostname``
    (HTTPS only) and the ``Host`` header, set by the adapter before this
    connection is ever opened. Connecting to ``self.host`` is therefore
    already pinned; no manual ``socket.create_connection`` override needed.
    The post-connect ``getpeername()`` re-check stays as defense-in-depth.
    """

    def __init__(
        self,
        *args: Any,
        address_checker: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._address_checker = address_checker or default_address_allowed

    def _new_conn(self) -> socket.socket:
        sock = super()._new_conn()
        peer = sock.getpeername()[0]
        self._address_checker(peer)
        return sock


class _PinnedHTTPSConnection(HTTPSConnection):
    """See ``_PinnedHTTPConnection`` -- same split-identity contract."""

    def __init__(
        self,
        *args: Any,
        address_checker: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._address_checker = address_checker or default_address_allowed

    def _new_conn(self) -> socket.socket:
        sock = super()._new_conn()
        peer = sock.getpeername()[0]
        self._address_checker(peer)
        return sock


class _PinnedHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _PinnedHTTPConnection

    def __init__(
        self,
        *args: Any,
        address_checker: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        self.address_checker = address_checker
        super().__init__(*args, **kwargs)

    def _new_conn(self) -> HTTPConnection:
        self.conn_kw = dict(self.conn_kw)
        self.conn_kw["address_checker"] = self.address_checker
        return super()._new_conn()


class _PinnedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _PinnedHTTPSConnection

    def __init__(
        self,
        *args: Any,
        address_checker: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        self.address_checker = address_checker
        super().__init__(*args, **kwargs)

    def _new_conn(self) -> HTTPSConnection:
        self.conn_kw = dict(self.conn_kw)
        self.conn_kw["address_checker"] = self.address_checker
        return super()._new_conn()


# Split-identity (host_params["host"] = pinned IP) means the pool key is now
# a plain IP string -- urllib3's stock PoolKey already has fields for every
# standard kwarg requests sends (server_hostname, assert_hostname, etc.).
# `address_checker` and `assert_same_host` remain genuinely foreign to
# PoolKey's fixed NamedTuple; excluding just these two (down from four,
# pre-split-identity) avoids the same "unexpected keyword argument" crash
# without needing a custom pool-key field for the pin itself anymore.
_NON_POOL_KEY_FIELDS = frozenset({"address_checker", "assert_same_host"})


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

    def build_connection_pool_key_attributes(
        self, request: requests.PreparedRequest, verify: Any, cert: Any = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Split-identity pinning: PLACE (pool key + TCP target) is the
        validated pin; NAME (TLS SNI/cert + HTTP Host) stays the original
        hostname. Setting ``host_params["host"]`` to the pin (rather than
        mutating ``self.poolmanager.connection_pool_kw``, the prior
        approach) makes urllib3's own stock ``PoolKey`` -- keyed on
        ``(scheme, host, port)`` -- naturally pin-aware: two different
        validated IPs for the same hostname get two separate, isolated
        connection pools automatically, with zero custom PoolKey fields.
        This also closes the actual thread-safety bug the old approach
        had (shared adapter-instance dict mutated by every concurrent
        request) -- ``build_connection_pool_key_attributes()`` is
        ``requests``' own per-call override seam (see
        ``HTTPAdapter.get_connection_with_tls_context()``), so every
        request gets its own freshly computed, request-local kwargs.
        """
        host_params, pool_kwargs = super().build_connection_pool_key_attributes(request, verify, cert=cert)
        url = request.url or ""
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        scheme = parsed.scheme
        port = parsed.port or (443 if scheme == "https" else 80)
        started = time.monotonic()
        try:
            self.url_checker(url)
            ips = validate_resolved(hostname, port, self.address_checker)
        except Exception as exc:
            emit(
                EgressEvent(
                    endpoint_class="remote",
                    host=hostname,
                    port=port,
                    scheme=scheme,
                    deny_reason=classify_deny_reason(exc),
                    duration_ms=(time.monotonic() - started) * 1000,
                )
            )
            raise
        pinned = ips[0]
        request.headers["Host"] = _host_header(hostname, port, scheme)

        host_params["host"] = pinned
        pool_kwargs["address_checker"] = self.address_checker
        if scheme == "https":
            pool_kwargs["assert_hostname"] = hostname
            pool_kwargs["server_hostname"] = hostname

        emit(
            EgressEvent(
                endpoint_class="remote",
                host=hostname,
                resolved_ip=pinned,
                port=port,
                scheme=scheme,
                duration_ms=(time.monotonic() - started) * 1000,
            )
        )
        return host_params, pool_kwargs

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
        return super().send(
            request,
            stream=stream,
            timeout=timeout,
            verify=verify,
            cert=cert,
            proxies=None,
        )


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
    previous_max_redirects = sess.max_redirects
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
                exc = RedirectDenied(f"redirect limit {max_redirects} exceeded")
                _current_parsed = urlparse(current)
                emit(
                    EgressEvent(
                        endpoint_class="remote",
                        host=_current_parsed.hostname or "",
                        port=_current_parsed.port
                        or (443 if _current_parsed.scheme == "https" else 80),
                        scheme=_current_parsed.scheme,
                        redirect_count=hops,
                        deny_reason=classify_deny_reason(exc),
                    )
                )
                raise exc
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
        else:
            sess.max_redirects = previous_max_redirects


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


def build_pinned_httpx_client(
    *,
    address_checker: Callable[[str], None] | None = None,
    is_async: bool = False,
    **client_kwargs: Any,
) -> httpx.Client | httpx.AsyncClient:
    """Build an httpx.Client/AsyncClient hardened for SDKs that don't use ``requests``.

    True IP pinning (resolve-once, connect-to-that-literal-IP) requires a
    custom ``httpcore`` network backend -- out of scope here. This gives the
    two properties the vendor-host exemption in
    ``docs/v2/plans/2026-08-20-ssrf-defense-in-depth.md`` actually requires
    for a fixed, code-reviewed host: (1) redirects are never auto-followed
    (``follow_redirects=False``, explicit rather than relying on httpx's
    own default matching), and (2) every resolved A/AAAA for the request's
    host is checked against ``address_checker`` via a "request" event hook
    immediately before httpx's own connection attempt -- closing the "this
    fixed hostname now resolves somewhere it shouldn't" gap that a bare
    ``httpx.Client()`` leaves fully open. TLS certificate verification stays
    on (httpx's own ``verify=True`` default, not overridden here).

    Only for use with fixed, hardcoded, code-reviewed hosts (vendor SDK
    base URLs) -- never for a caller-supplied/arbitrary URL, which needs
    real pinning (``ssrf_request``) or must be routed through a
    caller-supplied-URL-safe path entirely.
    """
    checker = address_checker or default_address_allowed

    def _validate_request_host(request: httpx.Request) -> None:
        hostname = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        validate_resolved(hostname, port, checker)

    async def _validate_request_host_async(request: httpx.Request) -> None:
        _validate_request_host(request)

    if client_kwargs.pop("follow_redirects", False):
        raise SSRFPolicyError("pinned httpx clients must not follow redirects")
    client_kwargs["follow_redirects"] = False
    hooks = dict(client_kwargs.pop("event_hooks", None) or {})
    request_hooks = list(hooks.get("request", []))
    request_hooks.append(_validate_request_host_async if is_async else _validate_request_host)
    hooks["request"] = request_hooks
    client_kwargs["event_hooks"] = hooks

    cls = httpx.AsyncClient if is_async else httpx.Client
    return cls(**client_kwargs)
