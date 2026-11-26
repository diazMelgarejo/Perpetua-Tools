"""The OpenClaw gateway service must never name a node version: a stable link points at one nvm prefix."""

from __future__ import annotations

import json
import plistlib
from pathlib import Path

import pytest

from perpetua_tools import openclaw_runtime as rt

PIN = "2026.10.6"


def _node(home: Path, version: str, openclaw: str | None = PIN) -> Path:
    """Create a fake nvm node prefix, with a global openclaw of the given version when asked."""
    prefix = home / ".nvm" / "versions" / "node" / f"v{version}"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin" / "node").write_text("#!/bin/sh\n", encoding="utf-8")
    if openclaw is not None:
        pkg = prefix / "lib" / "node_modules" / "openclaw"
        (pkg / "dist").mkdir(parents=True)
        (pkg / "package.json").write_text(json.dumps({"version": openclaw}), encoding="utf-8")
        (pkg / "dist" / "index.js").write_text("// entry\n", encoding="utf-8")
    return prefix


def _plist(home: Path, prefix: Path, port: int = 18789) -> Path:
    path = home / "Library" / "LaunchAgents" / "ai.openclaw.gateway.plist"
    path.parent.mkdir(parents=True)
    args = ["/bin/sh", str(home / ".openclaw" / "service-env" / "wrapper.sh"), str(home / "x.env"),
            str(prefix / "bin" / "node"), "--max-old-space-size=8192",
            str(prefix / "lib" / "node_modules" / "openclaw" / "dist" / "index.js"), "gateway", "--port", str(port)]
    path.write_bytes(plistlib.dumps({"Label": "ai.openclaw.gateway", "KeepAlive": True, "ProgramArguments": args}))
    return path


def _pin(home: Path, version: str = PIN) -> None:
    pkg = home / ".alphaclaw" / "node_modules" / "@diazmelgarejo" / "alphaclaw"
    pkg.mkdir(parents=True)
    (pkg / "package.json").write_text(json.dumps({"dependencies": {"openclaw": version}}), encoding="utf-8")


class Fake:
    """A launchd that records calls: bootout unloads the service, bootstrap loads it (and can fail first)."""

    def __init__(self, answering: bool = True, bootstrap_failures: int = 0) -> None:
        self.calls: list[list[str]] = []
        self.answering = answering
        self.bootstrap_failures = bootstrap_failures
        self.loaded = True

    def run(self, cmd: list[str]) -> int:
        self.calls.append(cmd)
        if cmd[1] == "bootout":
            self.loaded = False
        elif cmd[1] == "bootstrap":
            if self.bootstrap_failures > 0:
                self.bootstrap_failures -= 1
                return 5  # launchd's I/O error while the old service is still being torn down
            self.loaded = True
        return 0

    def probe(self, port: int) -> bool:
        return self.answering and self.loaded

    def count(self, verb: str) -> int:
        return sum(1 for c in self.calls if c[1] == verb)


def _paths(home: Path) -> rt.Paths:
    return rt.Paths.under(home)


@pytest.mark.parametrize(("raw", "ok"), [("24.22.1", True), ("24.22.3", True), ("24.22.0", False), ("24.14.1", False),
                                          ("25.0.0", False), ("26.12.1", True), ("26.13.0", True), ("22.22.2", False)])
def test_engines_range_matches_the_alphaclaw_and_openclaw_requirement(raw: str, ok: bool) -> None:
    assert rt.satisfies_engines(rt.parse_version(f"v{raw}")) is ok


def test_selection_takes_the_highest_node_that_fits_the_range_and_carries_the_pinned_openclaw(tmp_path: Path) -> None:
    _node(tmp_path, "24.14.1")                      # too old
    _node(tmp_path, "24.22.3")
    _node(tmp_path, "24.22.5", openclaw=None)       # no openclaw installed under it
    _node(tmp_path, "24.22.6", openclaw="2026.7.1") # wrong openclaw version
    chosen = rt.select(rt.discover(_paths(tmp_path).nvm), PIN)
    assert chosen is not None and chosen.prefix.name == "v24.22.3"


def test_selection_returns_none_when_nothing_fits(tmp_path: Path) -> None:
    _node(tmp_path, "24.14.1")
    assert rt.select(rt.discover(_paths(tmp_path).nvm), PIN) is None


def test_plist_arguments_lose_every_version_literal_and_rewriting_twice_changes_nothing(tmp_path: Path) -> None:
    prefix = _node(tmp_path, "24.22.3")
    args = ["/bin/sh", "w.sh", str(prefix / "bin" / "node"), str(prefix / "lib" / "node_modules" / "openclaw" / "dist" / "index.js"), "gateway"]
    link = tmp_path / ".local" / "share" / "openclaw-node"
    once = rt.rewrite_arguments(args, link)
    assert once == ["/bin/sh", "w.sh", f"{link}/bin/node", f"{link}/lib/node_modules/openclaw/dist/index.js", "gateway"]
    assert not any("/versions/node/v" in a for a in once) and rt.rewrite_arguments(once, link) == once


def test_a_fresh_install_reports_drift_and_apply_fixes_it_idempotently(tmp_path: Path) -> None:
    prefix = _node(tmp_path, "24.22.3")
    plist = _plist(tmp_path, prefix)
    _pin(tmp_path)
    paths, fake = _paths(tmp_path), Fake()
    assert {f.code for f in rt.inspect(paths)} == {"link-missing", "plist-hardwired"}
    rt.apply(paths, run=fake.run, probe=fake.probe)
    assert paths.link.is_symlink() and paths.link.resolve() == prefix.resolve()
    args = plistlib.loads(plist.read_bytes())["ProgramArguments"]
    assert str(paths.link) in " ".join(args) and "/versions/node/v" not in " ".join(args)
    assert rt.inspect(paths) == []
    before = len(fake.calls)
    rt.apply(paths, run=fake.run, probe=fake.probe)
    assert len(fake.calls) == before, "an already-correct install must not reload the service"


def test_a_node_upgrade_is_one_repoint_and_one_reload(tmp_path: Path) -> None:
    old = _node(tmp_path, "24.22.3")
    _plist(tmp_path, old)
    _pin(tmp_path)
    paths, fake = _paths(tmp_path), Fake()
    rt.apply(paths, run=fake.run, probe=fake.probe)
    new = _node(tmp_path, "24.22.4")
    assert [f.code for f in rt.inspect(paths)] == ["link-stale"]
    before = len(fake.calls)
    rt.apply(paths, run=fake.run, probe=fake.probe)
    assert paths.link.resolve() == new.resolve() and len(fake.calls) > before
    assert rt.inspect(paths) == []


def test_removing_the_linked_node_is_reported_as_a_dangling_link(tmp_path: Path) -> None:
    prefix = _node(tmp_path, "24.22.3")
    _plist(tmp_path, prefix)
    _pin(tmp_path)
    paths, fake = _paths(tmp_path), Fake()
    rt.apply(paths, run=fake.run, probe=fake.probe)
    (prefix / "bin" / "node").unlink()
    assert "link-dangling" in {f.code for f in rt.inspect(paths)}


def test_apply_touches_nothing_when_no_node_satisfies_the_pinned_openclaw(tmp_path: Path) -> None:
    prefix = _node(tmp_path, "24.14.1")
    plist = _plist(tmp_path, prefix)
    _pin(tmp_path)
    before = plist.read_bytes()
    paths, fake = _paths(tmp_path), Fake()
    with pytest.raises(rt.RuntimeSyncError):
        rt.apply(paths, run=fake.run, probe=fake.probe)
    assert plist.read_bytes() == before and fake.calls == [] and not paths.link.exists()


def test_a_bootstrap_that_fails_while_the_old_service_is_torn_down_is_retried(tmp_path: Path) -> None:
    """Regression 2026-11-25: bootout is asynchronous, so the first bootstrap can fail; it must be retried."""
    prefix = _node(tmp_path, "24.22.3")
    _plist(tmp_path, prefix)
    _pin(tmp_path)
    paths, fake = _paths(tmp_path), Fake(bootstrap_failures=2)
    rt.apply(paths, run=fake.run, probe=fake.probe, retry_delay=0)
    assert fake.count("bootstrap") == 3 and fake.loaded


def test_a_bootstrap_that_never_succeeds_is_an_error_that_says_the_service_is_unloaded(tmp_path: Path) -> None:
    prefix = _node(tmp_path, "24.22.3")
    _plist(tmp_path, prefix)
    _pin(tmp_path)
    paths, fake = _paths(tmp_path), Fake(bootstrap_failures=99)
    with pytest.raises(rt.RuntimeSyncError, match="bootstrap failed.*unloaded"):
        rt.apply(paths, run=fake.run, probe=fake.probe, retry_delay=0)


def test_the_probe_is_not_trusted_until_the_old_service_has_released_the_port(tmp_path: Path) -> None:
    """Regression 2026-11-25: a probe taken before the old process died passed and hid an unloaded service."""
    prefix = _node(tmp_path, "24.22.3")
    _plist(tmp_path, prefix)
    _pin(tmp_path)
    paths, fake = _paths(tmp_path), Fake()
    order: list[str] = []
    real_run, real_probe = fake.run, fake.probe

    def run(cmd: list[str]) -> int:
        order.append(cmd[1])
        return real_run(cmd)

    def probe(port: int) -> bool:
        answer = real_probe(port)
        order.append(f"probe:{answer}")
        return answer

    rt.apply(paths, run=run, probe=probe, retry_delay=0)
    assert order.index("bootout") < order.index("probe:False") < order.index("bootstrap") < order.index("probe:True")


def test_a_gateway_that_does_not_answer_after_the_reload_is_an_error(tmp_path: Path) -> None:
    prefix = _node(tmp_path, "24.22.3")
    _plist(tmp_path, prefix)
    _pin(tmp_path)
    paths, fake = _paths(tmp_path), Fake(answering=False)
    with pytest.raises(rt.RuntimeSyncError, match="did not answer"):
        rt.apply(paths, run=fake.run, probe=fake.probe, wait_seconds=0)


def test_bootstrap_step_reports_drift_without_raising_or_changing_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The default AlphaClaw bootstrap warns about a version-named service and never blocks the start."""
    from perpetua_tools import alphaclaw_bootstrap as boot

    prefix = _node(tmp_path, "24.22.3")
    plist = _plist(tmp_path, prefix)
    _pin(tmp_path)
    before = plist.read_bytes()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(boot.sys, "platform", "darwin")
    boot._check_runtime_link()
    out = capsys.readouterr().out
    assert "plist-hardwired" in out and "openclaw_runtime --apply" in out
    assert plist.read_bytes() == before
    monkeypatch.setattr(boot.sys, "platform", "linux")
    boot._check_runtime_link()
    assert capsys.readouterr().out == "", "no launch agent exists off macOS, so the step stays silent"


def test_cli_check_exits_nonzero_on_drift_and_zero_when_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    prefix = _node(tmp_path, "24.22.3")
    _plist(tmp_path, prefix)
    _pin(tmp_path)
    assert rt.main(["--check", "--home", str(tmp_path)]) == 1
    assert "plist-hardwired" in capsys.readouterr().out
    rt.apply(_paths(tmp_path), run=Fake().run, probe=Fake().probe)
    assert rt.main(["--check", "--home", str(tmp_path)]) == 0


def test_custom_nvm_dir_is_discovered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom_nvm = tmp_path / "custom_nvm"
    prefix = custom_nvm / "versions" / "node" / "v24.22.3"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin" / "node").write_text("#!/bin/sh\n", encoding="utf-8")
    pkg = prefix / "lib" / "node_modules" / "openclaw"
    (pkg / "dist").mkdir(parents=True)
    (pkg / "package.json").write_text(json.dumps({"version": PIN}), encoding="utf-8")
    _pin(tmp_path)
    monkeypatch.setenv("NVM_DIR", str(custom_nvm))
    paths = rt.Paths.under(tmp_path)
    installs = rt.discover(paths.nvm)
    assert len(installs) == 1 and installs[0].version == (24, 22, 3)


def test_homebrew_node_alias_is_rewritten_to_link(tmp_path: Path) -> None:
    link = tmp_path / ".local" / "share" / "openclaw-node"
    args = ["/bin/sh", "/path/wrapper.sh", "/opt/homebrew/bin/node", "--max-old-space-size=8192", "gateway"]
    rewritten = rt.rewrite_arguments(args, link)
    assert rewritten == ["/bin/sh", "/path/wrapper.sh", f"{link}/bin/node", "--max-old-space-size=8192", "gateway"]


def test_apply_reloads_when_service_is_unloaded_despite_consistent_files(tmp_path: Path) -> None:
    prefix = _node(tmp_path, "24.22.3")
    _plist(tmp_path, prefix)
    _pin(tmp_path)
    fake = Fake(answering=True)
    paths = _paths(tmp_path)
    # First apply makes files consistent and loads service
    rt.apply(paths, run=fake.run, probe=fake.probe)
    # Simulate service becoming unloaded later (e.g. earlier failed bootstrap or crashed service)
    fake.loaded = False
    assert not fake.probe(18789)
    # Second apply sees no file drift, but recognizes unloaded gateway and triggers reload
    actions = rt.apply(paths, run=fake.run, probe=fake.probe)
    assert "reloaded the launch agent" in actions
    assert fake.loaded is True
