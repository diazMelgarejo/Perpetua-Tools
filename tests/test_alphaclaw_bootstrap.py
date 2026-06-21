from __future__ import annotations

import asyncio
import builtins
from pathlib import Path

import perpetua_tools.alphaclaw_bootstrap as alphaclaw_bootstrap


def test_start_openclaw_gateway_closes_log_handle_when_popen_fails(tmp_path, monkeypatch):
    real_open = builtins.open
    opened = []

    class TrackingFile:
        def __init__(self, fh):
            self._fh = fh
            self.closed_by_wrapper = False

        def close(self):
            self.closed_by_wrapper = True
            return self._fh.close()

        def __getattr__(self, name):
            return getattr(self._fh, name)

    def tracking_open(file, *args, **kwargs):
        fh = TrackingFile(real_open(file, *args, **kwargs))
        opened.append(fh)
        return fh

    def fail_popen(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr(alphaclaw_bootstrap.shutil, "which", lambda _name: "openclaw")
    monkeypatch.setattr(alphaclaw_bootstrap.subprocess, "Popen", fail_popen)
    monkeypatch.setattr(builtins, "open", tracking_open)

    result = asyncio.run(
        alphaclaw_bootstrap._start_openclaw_gateway(
            Path(tmp_path),
            setup_password="secret",
            timeout=0,
        )
    )

    assert result is None
    assert opened
    assert opened[0].closed_by_wrapper is True
