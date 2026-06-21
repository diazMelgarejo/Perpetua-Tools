"""oramaclaw V1 — command-line interface.

Entry point: ``main(argv=None) -> int``

Subcommands
-----------
apply <manifest>     Parse manifest, resolve target, run ControlEngine.
status               Show last transaction state and open-conflict count.
resolve <id> <choice>  Mark a pending conflict resolution.
targets list         List named targets from the catalog.
targets add <name>   Stub (V2 feature).

Exit codes
----------
0 — success / committed / auto_woven
1 — needs_input / conflicted / not-found
2 — gateway_unavailable / failed / unexpected exception
"""
from __future__ import annotations

import argparse
import sys
import traceback
from typing import Sequence

from oramaclaw.engine import ControlEngine
from oramaclaw.schema import parse_manifest
from oramaclaw.store import ControlStore
from oramaclaw.target import TargetCatalog, resolve_target

# ── Exit code constants ───────────────────────────────────────────────────────

_EXIT_OK = 0
_EXIT_NEEDS_INPUT = 1
_EXIT_FAILED = 2

# States that map to each exit code.
_STATES_OK = {"committed", "auto_woven"}
_STATES_NEEDS_INPUT = {"needs_input", "conflicted"}
_STATES_FAILED = {"gateway_unavailable", "failed"}

_TARGET_HELP = (
    "Named target from catalog "
    "($ORAMACLAW_TARGETS_PATH or ~/.openclaw/oramaclaw-targets.json)"
)


# ── Argument parser ────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oramaclaw",
        description="oramaclaw V1 control plane",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # Shared flags for target resolution.
    target_parent = argparse.ArgumentParser(add_help=False)
    target_parent.add_argument("--workspace", metavar="PATH", default=None,
                               help="Workspace root path")
    target_parent.add_argument("--config-path", metavar="PATH", default=None,
                               dest="config_path",
                               help="Path to openclaw.json")
    target_parent.add_argument("--state-dir", metavar="PATH", default=None,
                               dest="state_dir",
                               help="State directory path")
    target_parent.add_argument("--target", metavar="NAME", default=None,
                               dest="target_name",
                               help=_TARGET_HELP)

    # ── apply ──────────────────────────────────────────────────────────────
    apply_p = sub.add_parser(
        "apply",
        parents=[target_parent],
        help="Apply a control manifest to a target",
    )
    apply_p.add_argument("manifest", metavar="<manifest>",
                         help="Path to the manifest JSON file")
    apply_p.add_argument("--dry-run", action="store_true", default=False,
                         help="Parse and resolve without calling the engine")

    # ── status ─────────────────────────────────────────────────────────────
    sub.add_parser(
        "status",
        parents=[target_parent],
        help="Show last transaction state and open-conflict count",
    )

    # ── resolve ────────────────────────────────────────────────────────────
    resolve_p = sub.add_parser(
        "resolve",
        parents=[target_parent],
        help="Record a choice for a pending conflict resolution",
    )
    resolve_p.add_argument("resolution_id", metavar="<resolution-id>",
                           help="Opaque resolution ID from a conflict record")
    resolve_p.add_argument("choice", metavar="<choice>",
                           help="Chosen option (e.g. apply-desired, keep-current)")

    # ── targets ────────────────────────────────────────────────────────────
    targets_p = sub.add_parser("targets", help="Manage named targets")
    targets_sub = targets_p.add_subparsers(dest="targets_command",
                                           metavar="<subcommand>")
    targets_sub.required = True

    targets_sub.add_parser("list", help="List all named targets")

    targets_add = targets_sub.add_parser("add", help="Add a named target (V2 stub)")
    targets_add.add_argument("name", metavar="<name>", help="Target name")
    targets_add.add_argument("--workspace", metavar="PATH", required=True,
                             help="Workspace root path")
    targets_add.add_argument("--config-path", metavar="PATH", default=None,
                             dest="config_path",
                             help="Path to openclaw.json")
    targets_add.add_argument("--state-dir", metavar="PATH", default=None,
                             dest="state_dir",
                             help="State directory path")

    return parser


# ── Sub-command handlers ───────────────────────────────────────────────────────

def _cmd_apply(args: argparse.Namespace) -> int:
    from pathlib import Path

    manifest_path = Path(args.manifest)
    manifest = parse_manifest(manifest_path)

    target = resolve_target(
        workspace=args.workspace,
        config_path=args.config_path,
        state_dir=args.state_dir,
        manifest=manifest,
        target_name=args.target_name,
    )

    if args.dry_run:
        print(
            f"[dry-run] manifest={manifest_path} "
            f"resources={len(manifest.resources)} target={target.workspace_root}"
        )
        return _EXIT_OK

    result = ControlEngine().apply_manifest(manifest, target)

    conflict_count = len(result.conflicts)
    applied_count = len(result.applied)
    auto_woven_count = len(result.auto_woven)

    print(
        f"state={result.state} "
        f"applied={applied_count} "
        f"auto_woven={auto_woven_count} "
        f"conflicts={conflict_count} "
        f"tx={result.transaction_id}"
    )
    if result.warnings:
        for w in result.warnings:
            print(f"  warning: {w}")

    if result.state in _STATES_OK:
        return _EXIT_OK
    if result.state in _STATES_NEEDS_INPUT:
        return _EXIT_NEEDS_INPUT
    return _EXIT_FAILED


def _cmd_status(args: argparse.Namespace) -> int:
    target = resolve_target(
        workspace=args.workspace,
        config_path=args.config_path,
        state_dir=args.state_dir,
        target_name=args.target_name,
    )

    with ControlStore.open(target) as store:
        last = store.last_transaction()
        conflicts = store.open_conflicts()

    if last is None:
        print("No transactions recorded.")
    else:
        print(
            f"last_transaction: state={last.get('state')} "
            f"tx={last.get('transaction_id')}"
        )
    print(f"open_conflicts={len(conflicts)}")
    return _EXIT_OK


def _cmd_resolve(args: argparse.Namespace) -> int:
    target = resolve_target(
        workspace=args.workspace,
        config_path=args.config_path,
        state_dir=args.state_dir,
        target_name=args.target_name,
    )

    with ControlStore.open(target) as store:
        found = store.resolve_pending(args.resolution_id, args.choice)

    if found:
        print(f"Resolved {args.resolution_id} → {args.choice}")
        return _EXIT_OK

    print(
        f"Error: resolution ID {args.resolution_id!r} not found.",
        file=sys.stderr,
    )
    return _EXIT_NEEDS_INPUT


def _cmd_targets_list() -> int:
    catalog = TargetCatalog.load()
    for name in catalog.names():
        print(name)
    return _EXIT_OK


def _cmd_targets_add(args: argparse.Namespace) -> int:  # noqa: ARG001
    print("targets add: not yet implemented (V2 feature)", file=sys.stderr)
    return _EXIT_NEEDS_INPUT


# ── Public entry point ────────────────────────────────────────────────────────

def main(argv: Sequence[str] | None = None) -> int:
    """Parse *argv* (or ``sys.argv[1:]``) and dispatch to the appropriate handler.

    Always returns an integer exit code; never raises to the caller.
    """
    try:
        parser = _build_parser()
        args = parser.parse_args(argv)

        command: str = args.command
        if command == "apply":
            return _cmd_apply(args)
        if command == "status":
            return _cmd_status(args)
        if command == "resolve":
            return _cmd_resolve(args)
        if command == "targets":
            if args.targets_command == "list":
                return _cmd_targets_list()
            if args.targets_command == "add":
                return _cmd_targets_add(args)

        # Should be unreachable — argparse enforces required subcommands.
        print(f"Error: unknown command {command!r}", file=sys.stderr)
        return _EXIT_FAILED

    except SystemExit as exc:
        # argparse calls sys.exit() for --help / errors; propagate the code.
        code = exc.code
        if isinstance(code, int):
            return code
        return _EXIT_FAILED if code is not None else _EXIT_OK

    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return _EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
