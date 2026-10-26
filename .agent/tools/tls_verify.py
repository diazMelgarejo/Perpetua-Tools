"""Verify a peer Portal TLS endpoint against its own CA (no token ever sent): health, unauthenticated 401, system-roots negative control, leaf SAN and expiry.

usage: python -I .agent/tools/tls_verify.py <ca_pem> <host> <port>
"""
import hashlib
import socket
import ssl
import sys
import urllib.error
import urllib.request

ca, host, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
print("ca_sha256_file", hashlib.sha256(open(ca, "rb").read()).hexdigest())


def get(path, ctx):
    """Return the HTTP status of a verified GET (or the exception class and reason for the negative control)."""
    try:
        with urllib.request.urlopen(f"https://{host}:{port}{path}", context=ctx, timeout=8) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # noqa: BLE001 - report the class for the negative control
        return f"{type(e).__name__}: {getattr(e, 'reason', e)}"


ctx = ssl.create_default_context(cafile=ca)
health = get("/health", ctx)
protected = get("/api/peer-inbox", ctx)
print("health (with CA)       ", health)
print("peer-inbox (no bearer) ", protected)
neg = ssl.create_default_context()  # negative control: system roots only
negative = get("/health", neg)
print("health (system roots)  ", negative)

with socket.create_connection((host, port), timeout=8) as s:
    with ctx.wrap_socket(s, server_hostname=host) as t:
        cert = t.getpeercert()
        print("leaf subject ", dict(x[0] for x in cert["subject"]))
        print("leaf SAN     ", cert.get("subjectAltName"))
        print("leaf notAfter", cert["notAfter"])

if health != 200 or protected not in {401, 403} or isinstance(negative, int):
    raise SystemExit(1)
