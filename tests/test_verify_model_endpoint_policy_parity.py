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
