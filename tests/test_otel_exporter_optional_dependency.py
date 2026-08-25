"""Regression coverage for importing the OTel exporter without OpenTelemetry."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap


def test_otel_exporter_dependency_absent_surface_is_stable() -> None:
    """Exercise the real fallback assignments in a clean interpreter."""
    repo_root = Path(__file__).resolve().parents[1]
    script = textwrap.dedent(
        """
        import builtins
        import sys

        repo_root = sys.argv[1]
        sys.path.insert(0, repo_root)
        real_import = builtins.__import__

        def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ModuleNotFoundError(f"blocked optional dependency: {name}")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = blocked_import
        import src.observability.otel_exporter as exporter

        assert exporter.HAS_OTEL is False
        assert exporter.HAS_OTLP_EXPORTER is False
        for name in (
            "otel_trace",
            "Resource",
            "TracerProvider",
            "BatchSpanProcessor",
            "OTLPSpanExporter",
        ):
            assert hasattr(exporter, name), name
            assert getattr(exporter, name) is None, name
        """
    )

    subprocess.run(
        [sys.executable, "-I", "-c", script, str(repo_root)],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
