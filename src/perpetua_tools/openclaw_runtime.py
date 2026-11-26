"""Keep the OpenClaw gateway service independent of any node version.

The gateway launch agent used to store the exact ``~/.nvm/versions/node/vX.Y.Z`` folder, so removing that
node, or upgrading past it, left a ``KeepAlive`` service crash-looping. This module makes one stable link own
the choice and keeps the service pointed at the link:

* ``~/.local/share/openclaw-node`` is a symlink to the highest installed nvm node that satisfies the engines
  range of AlphaClaw and openclaw (>=24.22.1 <25, or >=26.12.1) and carries the global openclaw version that
  AlphaClaw pins, so "global" and "AlphaClaw" stay the same version.
* The launch agent's ``ProgramArguments`` use the link, never a version.
* ``--check`` (default) is read-only and exits 1 on drift; ``--apply`` repoints the link, rewrites the plist
  and reloads the service only when something changed, then waits for the gateway to answer.

Decision record: operator-approved 2026-11-25, see the PT lesson on the stable runtime link.
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

LABEL = "ai.openclaw.gateway"
DEFAULT_PORT = 18789
ENGINE_FLOOR = (24, 22, 1)
ENGINE_CEILING = (25, 0, 0)
ENGINE_ALT_FLOOR = (26, 12, 1)
PIN_PACKAGES = ("@diazmelgarejo/alphaclaw", "@chrysb/alphaclaw")
_NODE_DIR = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_VERSIONED = re.compile(r"^(?P<root>.*/\.nvm/versions/node/v\d+\.\d+\.\d+)(?P<rest>/.*)$")

Version = tuple[int, int, int]


class RuntimeSyncError(RuntimeError):
    """The runtime could not be made consistent; nothing was changed unless the message says otherwise."""


@dataclass(frozen=True)
class Paths:
    home: Path
    nvm: Path
    link: Path
    plist: Path
    alphaclaw: Path

    @classmethod
    def under(cls, home: Path, nvm_dir: Path | None = None) -> "Paths":
        if nvm_dir is None:
            env_nvm = os.environ.get("NVM_DIR")
            if env_nvm and (home == Path.home() or not (home / ".nvm").exists()):
                nvm_dir = Path(env_nvm)
            else:
                nvm_dir = home / ".nvm"
        return cls(
            home=home,
            nvm=nvm_dir / "versions" / "node",
            link=home / ".local" / "share" / "openclaw-node",
            plist=home / "Library" / "LaunchAgents" / f"{LABEL}.plist",
            alphaclaw=home / ".alphaclaw" / "node_modules",
        )


@dataclass(frozen=True)
class NodeInstall:
    version: Version
    prefix: Path
    openclaw_version: str | None


@dataclass(frozen=True)
class Finding:
    code: str
    message: str


def parse_version(raw: str) -> Version:
    parts = raw.lstrip("v").split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def satisfies_engines(version: Version) -> bool:
    """True for node >=24.22.1 <25 or >=26.12.1, the range AlphaClaw 0.9.38+ and openclaw 2026.10.6 declare."""
    return (ENGINE_FLOOR <= version < ENGINE_CEILING) or version >= ENGINE_ALT_FLOOR


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def discover(nvm: Path) -> list[NodeInstall]:
    """Every nvm node that has a binary, with the version of the global openclaw installed under it."""
    found: list[NodeInstall] = []
    for entry in sorted(nvm.glob("v*")) if nvm.is_dir() else []:
        match = _NODE_DIR.match(entry.name)
        if not match or not (entry / "bin" / "node").is_file():
            continue
        manifest = entry / "lib" / "node_modules" / "openclaw" / "package.json"
        version = _read_json(manifest).get("version") if manifest.is_file() else None
        found.append(NodeInstall(tuple(int(g) for g in match.groups()), entry, version))  # type: ignore[arg-type]
    return found


def pinned_openclaw(paths: Paths) -> str | None:
    """The openclaw version the installed AlphaClaw package depends on: the single source of truth."""
    for name in PIN_PACKAGES:
        pin = _read_json(paths.alphaclaw / name / "package.json").get("dependencies", {}).get("openclaw")
        if pin:
            return str(pin)
    return None


def select(installs: list[NodeInstall], pin: str | None) -> NodeInstall | None:
    """Highest node that fits the engines range and carries the pinned openclaw (any version when unpinned)."""
    fits = [i for i in installs if satisfies_engines(i.version) and i.openclaw_version is not None
            and (pin is None or i.openclaw_version == pin)]
    return max(fits, key=lambda i: i.version, default=None)


def _versioned_suffix(arg: str, nvm: Path | None) -> str | None:
    """Return the ``/rest`` after a versioned node prefix, or None when unmatched.

    When ``nvm`` (``Paths.nvm`` → ``<nvm-root>/versions/node``) is set, only prefixes
    under that root match. Without it, fall back to the legacy ``/.nvm/versions/node/``
    regex so older call sites keep working.
    """
    if nvm is not None:
        root = str(nvm).rstrip("/")
        match = re.match(rf"^{re.escape(root)}/v\d+\.\d+\.\d+(/.*)$", arg)
        return match.group(1) if match else None
    match = _VERSIONED.match(arg)
    return match.group("rest") if match else None


def rewrite_arguments(args: list[str], link: Path, nvm: Path | None = None) -> list[str]:
    """Replace versioned node prefixes and Homebrew aliases with the stable link.

    Pass ``nvm`` (``Paths.nvm``) so custom ``NVM_DIR`` installs are rewritten; wrapper
    arguments and already-linked paths stay unchanged.
    """
    rewritten: list[str] = []
    for a in args:
        if a in ("/opt/homebrew/bin/node", "/usr/local/bin/node"):
            rewritten.append(f"{link}/bin/node")
        elif (rest := _versioned_suffix(a, nvm)) is not None:
            rewritten.append(f"{link}{rest}")
        else:
            rewritten.append(a)
    return rewritten


def _service_arguments(plist: Path) -> list[str]:
    return list(plistlib.loads(plist.read_bytes()).get("ProgramArguments", []))


def _port(args: list[str]) -> int:
    for flag, value in zip(args, args[1:]):
        if flag == "--port" and value.isdigit():
            return int(value)
    return DEFAULT_PORT


def inspect(paths: Paths) -> list[Finding]:
    """Read-only comparison of the link and the service file with the node the selection rule would choose."""
    findings: list[Finding] = []
    chosen = select(discover(paths.nvm), pinned_openclaw(paths))
    if chosen is None:
        findings.append(Finding("no-node", "no nvm node satisfies the engines range and carries the pinned openclaw"))
    if not paths.link.is_symlink():
        code = "link-not-symlink" if paths.link.exists() else "link-missing"
        findings.append(Finding(code, f"{paths.link} is not a symlink to a node prefix"))
    elif not (paths.link / "bin" / "node").is_file():
        findings.append(Finding("link-dangling", f"{paths.link} points at a node that no longer exists"))
    elif chosen is not None and paths.link.resolve() != chosen.prefix.resolve():
        findings.append(Finding("link-stale", f"{paths.link} targets {paths.link.resolve().name}, expected {chosen.prefix.name}"))
    if not paths.plist.is_file():
        findings.append(Finding("plist-missing", f"{paths.plist} does not exist; run: openclaw gateway install"))
    else:
        args = _service_arguments(paths.plist)
        if args != rewrite_arguments(args, paths.link, paths.nvm):
            findings.append(Finding("plist-hardwired", "the service file names a node version instead of the stable link"))
    return findings


def _atomic_symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    tmp = link.with_name(f".{link.name}.tmp")
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    tmp.symlink_to(target)
    os.replace(tmp, link)


def default_run(cmd: list[str]) -> int:
    return subprocess.run(cmd, capture_output=True, timeout=60, check=False).returncode


def default_probe(port: int) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=2):
            return True
    except OSError:
        return False


def _wait_for(condition: Callable[[], bool], seconds: float) -> bool:
    """Poll until the condition holds or the time is up; always evaluates it at least once."""
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)
    return True


def apply(
    paths: Paths,
    *,
    run: Callable[[list[str]], int] = default_run,
    probe: Callable[[int], bool] = default_probe,
    wait_seconds: float = 30.0,
    settle_seconds: float = 15.0,
    retry_delay: float = 2.0,
    bootstrap_attempts: int = 5,
) -> list[str]:
    """Make the link and the service file consistent, reload only on change, and confirm the gateway answers."""
    findings = {f.code for f in inspect(paths)}
    if not findings:
        if paths.plist.is_file():
            port = _port(_service_arguments(paths.plist))
            if probe(port):
                return []
        else:
            return []
    if "plist-missing" in findings:
        raise RuntimeSyncError("the service file is missing; run: openclaw gateway install, then apply again")
    if "link-not-symlink" in findings:
        raise RuntimeSyncError(f"{paths.link} exists and is not a symlink; move it aside first")
    chosen = select(discover(paths.nvm), pinned_openclaw(paths))
    if chosen is None:
        raise RuntimeSyncError("no nvm node satisfies node >=24.22.1 <25 (or >=26.12.1) and carries the pinned openclaw; "
                               "install it under a fitting node: npm install -g openclaw@<pinned>")
    actions: list[str] = []
    if findings & {"link-missing", "link-stale", "link-dangling"}:
        _atomic_symlink(chosen.prefix, paths.link)
        actions.append(f"linked {paths.link} -> {chosen.prefix.name}")
    args = _service_arguments(paths.plist)
    new_args = rewrite_arguments(args, paths.link, paths.nvm)
    if new_args != args:
        document = plistlib.loads(paths.plist.read_bytes())
        document["ProgramArguments"] = new_args
        tmp = paths.plist.with_name(f".{paths.plist.name}.tmp")
        tmp.write_bytes(plistlib.dumps(document))
        os.replace(tmp, paths.plist)
        actions.append("rewrote the service file to use the stable link")
    uid, port = os.getuid(), _port(new_args)
    run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"])  # not loaded is fine
    # bootout is asynchronous: a probe or a bootstrap taken before the old process is gone lies or fails
    # (2026-11-25: the probe passed against the dying service while the new one never loaded).
    _wait_for(lambda: not probe(port), settle_seconds)
    for attempt in range(1, bootstrap_attempts + 1):
        if run(["launchctl", "bootstrap", f"gui/{uid}", str(paths.plist)]) == 0:
            break
        if attempt < bootstrap_attempts:
            time.sleep(retry_delay)
    else:
        raise RuntimeSyncError(f"launchctl bootstrap failed {bootstrap_attempts} times and the service is unloaded; run: "
                               f"launchctl bootstrap gui/{uid} {paths.plist}")
    actions.append("reloaded the launch agent")
    deadline = time.monotonic() + wait_seconds
    while True:
        if probe(port):
            return actions
        if time.monotonic() >= deadline:
            raise RuntimeSyncError(f"the gateway did not answer on port {port} after the reload; the backup state is untouched")
        time.sleep(1.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keep the OpenClaw gateway service independent of any node version")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="read-only; exit 1 on drift (default)")
    mode.add_argument("--apply", action="store_true", help="repoint the link, rewrite the service file, reload once")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--home", type=Path, default=Path.home(), help="home directory (tests)")
    parser.add_argument("--nvm-dir", type=Path, default=None, help="custom nvm root directory (defaults to NVM_DIR or <home>/.nvm)")
    options = parser.parse_args(argv)
    paths = Paths.under(options.home, nvm_dir=options.nvm_dir)
    if options.apply:
        try:
            actions = apply(paths)
        except RuntimeSyncError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"actions": actions}) if options.json else "\n".join(actions or ["already consistent: nothing changed"]))
        return 0
    findings = inspect(paths)
    if options.json:
        print(json.dumps([f.__dict__ for f in findings]))
    else:
        print("\n".join(f"DRIFT {f.code}: {f.message}" for f in findings) or "OK: the gateway service uses the stable node link")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
