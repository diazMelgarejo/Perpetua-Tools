"""Regression checks for the Perpetua GossipBus thin wrapper."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / ".agents" / "skills" / "gossip-bus" / "SKILL.md"


def test_wrapper_resolves_only_through_shared_resolver() -> None:
    """Avoid accepting an arbitrary current Git root with a copied skill file."""
    before_load = WRAPPER.read_text(encoding="utf-8").split("## Load Canonical Skill", 1)[0]

    assert 'ROOT="$( . "$PT_ROOT/scripts/resolve_orama_root.sh" && resolve_orama_root )"' in before_load
    assert '"$PT_ROOT/bin/orama-system/skills/gossip-bus/SKILL.md"' not in before_load


def test_refresh_exits_when_the_canonical_skill_directory_is_missing() -> None:
    """Prevent a failed directory change from fetching in the caller's repository."""
    refresh = WRAPPER.read_text(encoding="utf-8").split("## Refresh", 1)[1]

    assert 'cd "$ROOT/bin/orama-system/skills/gossip-bus" || exit 1' in refresh
