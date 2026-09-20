"""Tests for verify_model_endpoint_policy_parity.py's core comparison logic."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "review"
    / "verify_model_endpoint_policy_parity.py"
)
_spec = importlib.util.spec_from_file_location("verify_parity", _SCRIPT_PATH)
verify_parity = importlib.util.module_from_spec(_spec)
sys.modules["verify_parity"] = verify_parity
_spec.loader.exec_module(verify_parity)


_MODEL_ENDPOINT_SRC = '''
def _host_allowed(host: str) -> bool:
    """docstring differs, should not matter."""
    return host == "localhost"


def validate_model_endpoint_url(url: str) -> str:
    return url


def parse_model_endpoint_list(raw: str) -> list[str]:
    return raw.split(",")
'''

_ENDPOINT_CORE_SRC = '''
def parse_transport_identity(raw: str):
    """some docstring."""
    return raw


def build_transport_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"
'''


def _write(tmp_path: Path, name: str, src: str) -> Path:
    p = tmp_path / name
    p.write_text(src, encoding="utf-8")
    return p


def test_files_to_check_includes_both_model_endpoint_url_and_endpoint_policy_core():
    """Regression: the parity checker only ever compared model_endpoint_url.py.
    endpoint_policy_core.py (parse_transport_identity/build_transport_url) is
    a second, separately-owned shared module with the exact same sync-drift
    risk and had zero parity coverage. FILES_TO_CHECK must list both."""
    names = {spec.filename for spec in verify_parity.FILES_TO_CHECK}
    assert "model_endpoint_url.py" in names
    assert "endpoint_policy_core.py" in names


def test_extract_policy_source_ignores_docstring_differences(tmp_path):
    identical_but_docstring = _MODEL_ENDPOINT_SRC.replace(
        '"""docstring differs, should not matter."""', '"""a totally different docstring."""'
    )
    a = _write(tmp_path, "a.py", _MODEL_ENDPOINT_SRC)
    b = _write(tmp_path, "b.py", identical_but_docstring)
    funcs = ("_host_allowed", "validate_model_endpoint_url", "parse_model_endpoint_list")
    assert verify_parity._extract_policy_source(a, funcs) == verify_parity._extract_policy_source(b, funcs)


def test_extract_policy_source_detects_real_logic_drift(tmp_path):
    drifted = _MODEL_ENDPOINT_SRC.replace('host == "localhost"', 'host != "localhost"')
    a = _write(tmp_path, "a.py", _MODEL_ENDPOINT_SRC)
    b = _write(tmp_path, "b.py", drifted)
    funcs = ("_host_allowed", "validate_model_endpoint_url", "parse_model_endpoint_list")
    assert verify_parity._extract_policy_source(a, funcs) != verify_parity._extract_policy_source(b, funcs)


def test_extract_policy_source_works_for_endpoint_policy_core_functions(tmp_path):
    a = _write(tmp_path, "a.py", _ENDPOINT_CORE_SRC)
    funcs = ("parse_transport_identity", "build_transport_url")
    src = verify_parity._extract_policy_source(a, funcs)
    assert "parse_transport_identity" in src
    assert "build_transport_url" in src


def test_extract_policy_source_raises_on_missing_function(tmp_path):
    incomplete = "def build_transport_url(host, port):\n    return host\n"
    a = _write(tmp_path, "a.py", incomplete)
    funcs = ("parse_transport_identity", "build_transport_url")
    with pytest.raises(SystemExit, match="parse_transport_identity"):
        verify_parity._extract_policy_source(a, funcs)


def test_files_to_check_model_endpoint_includes_is_loopback_host():
    """Task B2 (lockstep heal): _is_loopback_host is the function that
    actually classifies whether a hostname is loopback -- omitting it from
    policy_functions meant parity could pass while that specific function
    diverged, exactly the class of bug PR #395 itself fixed."""
    spec = next(s for s in verify_parity.FILES_TO_CHECK if s.filename == "model_endpoint_url.py")
    assert "_is_loopback_host" in spec.policy_functions


def test_files_to_check_model_endpoint_requires_identical_bytes():
    specs = {s.filename: s for s in verify_parity.FILES_TO_CHECK}
    assert specs["model_endpoint_url.py"].require_identical_bytes is True
    assert specs["endpoint_policy_core.py"].require_identical_bytes is False


def test_model_endpoint_byte_hash_detects_docstring_only_drift(tmp_path):
    funcs = ("_host_allowed", "validate_model_endpoint_url", "parse_model_endpoint_list", "_is_loopback_host")
    src_with_loopback = _MODEL_ENDPOINT_SRC + (
        "\n\ndef _is_loopback_host(host: str) -> bool:\n    return host == \"localhost\"\n"
    )
    drifted_docstring_only = src_with_loopback.replace(
        '"""docstring differs, should not matter."""', '"""a completely different module comment."""'
    )
    (tmp_path / "local").mkdir()
    (tmp_path / "peer").mkdir()
    local = _write(tmp_path / "local", "model_endpoint_url.py", src_with_loopback)
    peer = _write(tmp_path / "peer", "model_endpoint_url.py", drifted_docstring_only)
    spec = verify_parity._FileSpec("model_endpoint_url.py", funcs, require_identical_bytes=True)

    assert verify_parity._extract_policy_source(local, funcs) == verify_parity._extract_policy_source(peer, funcs)
    assert verify_parity._check_one(spec, local.parent, peer.parent) is False


def test_check_one_fails_when_peer_file_missing_for_either_file(tmp_path):
    """S4 (lockstep heal): _check_one previously printed 'skip' and
    returned True when the peer FILE was missing -- skip-success,
    indistinguishable from a real pass. Applies to both files now
    (plan Task 4: 'prefer fail both on main after PR 363')."""
    (tmp_path / "local").mkdir()
    (tmp_path / "peer").mkdir()
    local = _write(tmp_path / "local", "endpoint_policy_core.py", _ENDPOINT_CORE_SRC)
    funcs = ("parse_transport_identity", "build_transport_url")
    spec = verify_parity._FileSpec("endpoint_policy_core.py", funcs)

    assert verify_parity._check_one(spec, local.parent, tmp_path / "peer") is False


def test_main_fails_closed_when_sibling_missing(monkeypatch):
    """S3 (lockstep heal): main() previously printed 'skip' and returned 0
    when the orama-system sibling wasn't found."""
    monkeypatch.setattr(verify_parity, "_sibling_utils_dir", lambda: None)
    monkeypatch.delenv("PARITY_ALLOW_MISSING_SIBLING", raising=False)
    assert verify_parity.main() != 0


def test_main_allows_missing_sibling_only_with_explicit_local_opt_out(monkeypatch):
    monkeypatch.setattr(verify_parity, "_sibling_utils_dir", lambda: None)
    monkeypatch.setenv("PARITY_ALLOW_MISSING_SIBLING", "1")
    assert verify_parity.main() == 0
