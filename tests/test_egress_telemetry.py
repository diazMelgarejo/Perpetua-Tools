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

from src.utils.egress_telemetry import EgressEvent, _sink_path, classify_deny_reason, emit
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
