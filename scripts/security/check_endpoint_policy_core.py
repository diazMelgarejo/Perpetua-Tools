#!/usr/bin/env python3
"""Check endpoint transport policy wiring.

This is intentionally structural: unit tests validate behavior, while this
script verifies that routing code and CI continue to use the shared policy
boundary instead of reintroducing local URL reconstruction.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = "config/endpoint-policy-contract.yml"

REQUIRED_FILES = [
    "src/utils/endpoint_policy_core.py",
    "tests/test_endpoint_policy_core.py",
    "tests/test_scheme_preservation.py",
    "tests/test_hardware_routing.py",
    "scripts/security/check_endpoint_policy_core.py",
    CONTRACT_PATH,
    ".github/workflows/security-invariants.yml",
    "AGENTS.md",
]

WORKFLOWS = [
    ".github/workflows/security-invariants.yml",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def fail(message: str) -> None:
    raise SystemExit(f"endpoint policy invariant failed: {message}")


def assert_required_files() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")


def assert_model_registry_uses_core() -> None:
    text = read("orchestrator/model_registry.py")
    if "from utils.endpoint_policy_core import build_transport_url" not in text:
        fail("model_registry.py must import build_transport_url from endpoint_policy_core")
    if "from urllib.parse import urlparse" in text or "urlparse(" in text:
        fail("model_registry.py must not parse transport URLs directly")
    if "http://{hostname}" in text or "http://{host}" in text:
        fail("model_registry.py must not hardcode http reconstruction")


def assert_fastapi_uses_core() -> None:
    text = read("orchestrator/fastapi_app.py")
    if "from utils.endpoint_policy_core import build_transport_url" not in text:
        fail("fastapi_app.py must import build_transport_url from endpoint_policy_core")
    if "from urllib.parse import urlparse" in text or "urlparse(" in text:
        fail("fastapi_app.py must not parse transport URLs directly")


def assert_launcher_guards_port_access() -> None:
    text = read("src/perpetua_tools/agent_launcher.py")
    if "def _safe_port(" not in text:
        fail("agent_launcher.py must keep the _safe_port guarded accessor")
    for stale in ("_p_mac.port or", "_p_mac_lms.port or", "parsed.port or default_port"):
        if stale in text:
            fail(f"agent_launcher.py reintroduced unguarded port access: {stale!r}")


def assert_bootstrap_guards_port_access() -> None:
    text = read("src/perpetua_tools/alphaclaw_bootstrap.py")
    if "if parsed.port is not None:\n        return parsed.port" in text:
        fail("alphaclaw_bootstrap.py reintroduced unguarded ParseResult.port access")
    if "_gateway_port_from_url" in text and "except ValueError" not in text:
        fail("alphaclaw_bootstrap.py gateway port extraction must wrap ValueError")


def assert_core_owns_urlparse_boundary() -> None:
    text = read("src/utils/endpoint_policy_core.py")
    required = [
        "class TransportIdentity",
        "def parse_transport_identity",
        "def build_transport_url",
        "from urllib.parse import urlparse",
        "_ALLOWED_SCHEMES",
    ]
    missing = [needle for needle in required if needle not in text]
    if missing:
        fail(f"endpoint_policy_core.py missing expected boundary symbols: {', '.join(missing)}")


def assert_workflows_run_policy() -> None:
    for workflow in WORKFLOWS:
        text = read(workflow)
        if "tests/test_endpoint_policy_core.py" not in text:
            fail(f"{workflow} must run endpoint policy core tests")
        if "scripts/security/check_endpoint_policy_core.py" not in text:
            fail(f"{workflow} must run endpoint policy checker")


def assert_contract_names_peer_repos() -> None:
    text = read(CONTRACT_PATH)
    required = [
        "diazMelgarejo/Perpetua-Tools",
        "diazMelgarejo/orama-system",
        "endpoint-transport-policy",
        "controlled-urlparse-boundary",
        "backend-port-isolation",
        "config/endpoint-policy-contract.yml",
        ".github/workflows/endpoint-policy-contract.yml",
        "scripts/security/check_endpoint_policy_contract.py",
        "bin/orama-system/skills/oramasys-method/SKILL.md",
        "bin/orama-system/skills/oramasys-method/references/integrative-merge.md",
        "bin/orama-system/skills/git-history-surgery/SKILL.md",
        ".claude/skills/hardware-policy/SKILL.md",
    ]
    missing = [needle for needle in required if needle not in text]
    if missing:
        fail(f"contract missing required entries: {', '.join(missing)}")


def assert_agents_guidance_names_skills() -> None:
    text = read("AGENTS.md")
    required = [
        "Endpoint transport policy",
        "src/utils/endpoint_policy_core.py",
        "config/endpoint-policy-contract.yml",
        "bin/orama-system/skills/oramasys-method/SKILL.md",
        "bin/orama-system/skills/oramasys-method/references/integrative-merge.md",
        "bin/orama-system/skills/git-history-surgery/SKILL.md",
        ".claude/skills/hardware-policy/SKILL.md",
    ]
    missing = [needle for needle in required if needle not in text]
    if missing:
        fail(f"AGENTS.md missing required endpoint guidance: {', '.join(missing)}")


def assert_no_double_scheme_literals() -> None:
    for folder in ("orchestrator", "src"):
        for path in (ROOT / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "http://http" in text or "https://https" in text:
                fail(f"double-scheme literal found in {path.relative_to(ROOT)}")


def main() -> None:
    assert_required_files()
    assert_model_registry_uses_core()
    assert_fastapi_uses_core()
    assert_launcher_guards_port_access()
    assert_bootstrap_guards_port_access()
    assert_core_owns_urlparse_boundary()
    assert_workflows_run_policy()
    assert_contract_names_peer_repos()
    assert_agents_guidance_names_skills()
    assert_no_double_scheme_literals()
    print("endpoint policy invariants passed")


if __name__ == "__main__":
    main()
