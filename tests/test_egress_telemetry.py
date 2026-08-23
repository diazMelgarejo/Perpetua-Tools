"""test_egress_telemetry.py -- redaction and non-blocking behavior for src/utils/egress_telemetry.py

Covers: no raw host/IP ever appears in the emitted output, sink failures
never raise into the caller, and deny_reason enum coverage matches every
SSRFPolicyError/AddressDenied/RedirectDenied subtype from ssrf_pinned_adapter.py.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from utils.egress_telemetry import EgressEvent, _sink_path, classify_deny_reason, emit
from src.utils.ssrf_pinned_adapter import AddressDenied, RedirectDenied
from src.utils.ssrf_pinned_adapter import SSRFPolicyError as AdapterSSRFPolicyError


@pytest.fixture
def sink_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PERPETUA_TELEMETRY_DIR", str(tmp_path))
    return tmp_path


class TestRedaction:
    def test_raw_hostname_never_appears_in_output(self, sink_dir: Path) -> None:
        secret_host = "internal-service.corp.example.com"
        emit(EgressEvent(endpoint_class="remote", host=secret_host, port=443, scheme="https"))
        raw = _sink_path().read_text(encoding="utf-8")
        assert secret_host not in raw

    def test_raw_ip_never_appears_in_output(self, sink_dir: Path) -> None:
        secret_ip = "203.0.113.77"
        emit(
            EgressEvent(
                endpoint_class="remote",
                host="api.example.com",
                resolved_ip=secret_ip,
                port=443,
                scheme="https",
            )
        )
        raw = _sink_path().read_text(encoding="utf-8")
        assert secret_ip not in raw

    def test_host_and_ip_are_hashed_with_sha256_prefix(self, sink_dir: Path) -> None:
        emit(
            EgressEvent(
                endpoint_class="remote",
                host="api.example.com",
                resolved_ip="203.0.113.77",
                port=443,
                scheme="https",
            )
        )
        record = json.loads(_sink_path().read_text(encoding="utf-8").splitlines()[0])
        assert record["host_hash"].startswith("sha256:")
        assert record["resolved_ip_hash"].startswith("sha256:")

    def test_deny_reason_never_leaks_raw_exception_message(self, sink_dir: Path) -> None:
        secret_url_fragment = "internal-service.corp"
        exc = AddressDenied(f"blocked address for {secret_url_fragment}")
        reason = classify_deny_reason(exc)
        assert secret_url_fragment not in reason
        assert reason in {
            "metadata_ip",
            "rfc1918_unapproved",
            "redirect_limit",
            "scheme_disallowed",
            "userinfo_present",
            "dns_resolution_failed",
            "other",
        }

    def test_event_without_resolved_ip_omits_ip_hash(self, sink_dir: Path) -> None:
        emit(EgressEvent(endpoint_class="local", host="localhost", port=8000, scheme="http"))
        record = json.loads(_sink_path().read_text(encoding="utf-8").splitlines()[0])
        assert record["resolved_ip_hash"] is None


class TestNonBlocking:
    def test_emit_swallows_sink_write_failure(self, sink_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Point the sink at a path that cannot be created (parent is a file, not a dir).
        blocker = sink_dir / "not-a-directory"
        blocker.write_text("x", encoding="utf-8")
        monkeypatch.setenv("PERPETUA_TELEMETRY_DIR", str(blocker / "nested"))
        emit(EgressEvent(endpoint_class="remote", host="api.example.com", port=443, scheme="https"))
        # No exception raised -- that is the entire test.

    def test_emit_never_raises_on_malformed_event_field(self, sink_dir: Path) -> None:
        emit(EgressEvent(endpoint_class="remote", host="", port=443, scheme="https"))


class TestDenyReasonCoverage:
    def test_redirect_denied_maps_to_redirect_limit(self) -> None:
        assert classify_deny_reason(RedirectDenied("redirect limit 5 exceeded")) == "redirect_limit"

    def test_address_denied_metadata_ip_maps_to_metadata_ip(self) -> None:
        assert classify_deny_reason(AddressDenied("blocked address: 169.254.169.254")) == "metadata_ip"

    def test_address_denied_ipv6_metadata_maps_to_metadata_ip(self) -> None:
        assert classify_deny_reason(AddressDenied("blocked address: fd00:ec2::254")) == "metadata_ip"

    def test_address_denied_generic_maps_to_rfc1918_unapproved(self) -> None:
        assert classify_deny_reason(AddressDenied("blocked address: 10.0.0.5")) == "rfc1918_unapproved"

    def test_address_denied_dns_failure_maps_to_dns_resolution_failed(self) -> None:
        assert (
            classify_deny_reason(AddressDenied("DNS failed for 'bad.example': socket.gaierror"))
            == "dns_resolution_failed"
        )

    def test_ssrf_policy_error_scheme_maps_to_scheme_disallowed(self) -> None:
        assert (
            classify_deny_reason(AdapterSSRFPolicyError("scheme not allowed: 'ftp'"))
            == "scheme_disallowed"
        )

    def test_ssrf_policy_error_userinfo_maps_to_userinfo_present(self) -> None:
        assert classify_deny_reason(AdapterSSRFPolicyError("userinfo is not allowed")) == "userinfo_present"

    def test_unrecognized_exception_maps_to_other(self) -> None:
        assert classify_deny_reason(ValueError("something unexpected")) == "other"


class TestSinkRotation:
    def test_sink_path_rotates_daily(self) -> None:
        day1 = _sink_path(now=1735689600.0)  # 2025-01-01T00:00:00Z
        day2 = _sink_path(now=1735776000.0)  # 2025-01-02T00:00:00Z
        assert day1 != day2
        assert day1.name != day2.name


class TestImportPathConsistency:
    """Regression: this repo's convention (per every existing lazy import in
    orama_bridge.py itself, connectivity.py, perplexity_client.py, and this
    module's own docstring) is `from utils.<name>`, not `from src.utils.<name>`.
    src/ has no __init__.py (a PEP 420 namespace package) while
    src/utils/__init__.py exists, so pythonpath=["src","."] makes the two
    prefixes resolve to two DISTINCT sys.modules entries with independent
    module-level state -- including egress_telemetry's per-process _SALT.
    If ssrf_pinned_adapter.py, orama_bridge.py, and this test file don't all
    import egress_telemetry via the identical path, events emitted from one
    call site can be hashed with a different salt than events emitted from
    another, silently breaking "correlation works within a session"."""

    def test_every_egress_telemetry_import_site_resolves_to_the_same_module(self) -> None:
        # Reflect real production behavior: modules are imported once and
        # cached in sys.modules; whichever import happens first "wins" and
        # every subsequent import of the same dotted path reuses it. Import
        # each real call site the same way this repo's actual code does
        # (utils.<name>, per this module's own docstring and every existing
        # lazy import elsewhere) and confirm they all share one egress_telemetry
        # instance -- not a forced fresh reimport, which would create an
        # artificial fourth instance nothing in production ever touches.
        import utils.egress_telemetry as canonical
        import utils.ssrf_pinned_adapter as adapter_mod
        import orchestrator.orama_bridge as bridge_mod

        assert adapter_mod.emit is canonical.emit, (
            "ssrf_pinned_adapter.py's egress_telemetry import resolves to a "
            "different module instance than utils.egress_telemetry "
            "-- salts will diverge between call sites"
        )
        assert bridge_mod.emit is canonical.emit, (
            "orama_bridge.py's egress_telemetry import resolves to a "
            "different module instance than utils.egress_telemetry "
            "-- salts will diverge between call sites"
        )


class TestClassifyDenyReasonPrecision:
    """Regression: classify_deny_reason mislabeled operator-facing telemetry.
    No security/functional impact -- enforcement is intact -- but the
    redacted deny_reason enum was wrong for anything outside the three
    literal IMDS strings, and two branches did unguarded substring matching
    that could misclassify unrelated network/TLS errors as SSRF denials."""

    def test_link_local_outside_imds_literals_is_not_labeled_rfc1918(self) -> None:
        # 169.254.1.1 is link-local (169.254.0.0/16) but not one of the three
        # literal IMDS strings (169.254.169.254, fd00:ec2::254, 169.254.170.2)
        # and not RFC1918 (10/8, 172.16/12, 192.168/16) at all.
        exc = AddressDenied("blocked address: 169.254.1.1")
        assert classify_deny_reason(exc) == "link_local"

    def test_ipv6_link_local_is_not_labeled_rfc1918(self) -> None:
        exc = AddressDenied("blocked address: fe80::1")
        assert classify_deny_reason(exc) == "link_local"

    def test_loopback_is_not_labeled_rfc1918(self) -> None:
        exc = AddressDenied("blocked address: 127.0.0.1")
        assert classify_deny_reason(exc) == "loopback"

    def test_multicast_is_not_labeled_rfc1918(self) -> None:
        exc = AddressDenied("blocked address: 224.0.0.1")
        assert classify_deny_reason(exc) == "multicast"

    def test_ipv6_ula_is_not_labeled_rfc1918(self) -> None:
        exc = AddressDenied("blocked address: fc00::1")
        assert classify_deny_reason(exc) == "ula"

    def test_cgnat_is_not_labeled_rfc1918(self) -> None:
        exc = AddressDenied("blocked address: 100.64.0.1")
        assert classify_deny_reason(exc) == "cgnat"

    def test_genuine_rfc1918_still_labeled_correctly(self) -> None:
        assert classify_deny_reason(AddressDenied("blocked address: 10.0.0.1")) == "rfc1918_unapproved"
        assert classify_deny_reason(AddressDenied("blocked address: 172.16.0.1")) == "rfc1918_unapproved"
        assert classify_deny_reason(AddressDenied("blocked address: 192.168.0.1")) == "rfc1918_unapproved"

    def test_unrelated_exception_mentioning_scheme_is_not_misclassified(self) -> None:
        """A TLS error or URL-parser message that happens to contain the word
        "scheme" must not be misclassified as an SSRF policy denial -- only
        a genuine SSRFPolicyError should ever map to scheme_disallowed."""
        exc = ValueError("unsupported certificate scheme in handshake")
        assert classify_deny_reason(exc) == "other"

    def test_unrelated_exception_mentioning_userinfo_is_not_misclassified(self) -> None:
        exc = ValueError("URL parser rejected userinfo component")
        assert classify_deny_reason(exc) == "other"
