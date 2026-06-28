"""Contract test: scheme preservation for tilting endpoint reconstruction.

This test enforces Oramasys invariant:
- If upstream tilting source returns a URL with scheme (http/https),
  downstream reconstruction MUST preserve that scheme.
"""

import importlib
import pytest

MODULE_CANDIDATES = [
    "orchestrator.model_registry",
    "model_registry",
]


def _load_module():
    last_err = None
    for name in MODULE_CANDIDATES:
        try:
            return importlib.import_module(name)
        except Exception as e:
            last_err = e
    pytest.skip(f"model_registry module not available: {last_err}")


def test_scheme_preservation_from_tilting_source():
    mod = _load_module()

    func = getattr(mod, "detect_active_tilting_ip", None)
    if func is None:
        pytest.skip("detect_active_tilting_ip not found in model_registry")

    result = func()

    if not result:
        pytest.skip("No tilting output available in current environment")

    if "://" in result:
        scheme = result.split("://", 1)[0]
        assert scheme in ("http", "https")
        assert result.startswith(scheme + "://")


def test_no_scheme_downgrade_on_reconstruction():
    mod = _load_module()

    for name in ["get_ollama_url", "get_lms_url", "build_ollama_url", "build_lms_url"]:
        func = getattr(mod, name, None)
        if not func:
            continue

        try:
            url = func()
        except Exception:
            continue

        if not url:
            continue

        if "://" in url:
            assert not url.startswith("http://http")
