"""Machine-readable endpoint policy inventory and vector contract tests."""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest
import yaml

from utils.endpoint_policy_core import build_transport_url
from utils.model_endpoint_url import ModelEndpointPolicyError, validate_model_endpoint_url

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "config" / "endpoint-policy-importer-inventory.yml"
VECTORS_PATH = ROOT / "config" / "endpoint-policy-behavior-vectors.yml"
CONTRACT_PATH = ROOT / "config" / "endpoint-policy-contract.yml"

TARGET_MODULES = {
    "utils.endpoint_policy_core",
    "src.utils.endpoint_policy_core",
    "utils.model_endpoint_url",
    "src.utils.model_endpoint_url",
    "endpoint_policy",
    "utils.ssrf_fetch_policy",
    "src.utils.ssrf_fetch_policy",
    "utils.ssrf_pinned_adapter",
    "src.utils.ssrf_pinned_adapter",
}

CANONICAL_MODULES = {
    "src.utils.endpoint_policy_core": "utils.endpoint_policy_core",
    "src.utils.model_endpoint_url": "utils.model_endpoint_url",
    "src.utils.ssrf_fetch_policy": "utils.ssrf_fetch_policy",
    "src.utils.ssrf_pinned_adapter": "utils.ssrf_pinned_adapter",
}

ALLOWED_BOUNDARIES = {
    "transport reconstruction",
    "model-endpoint allow/deny",
    "published package compatibility",
    "SSRF preflight",
    "SSRF pinned transport",
}


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _tracked_python_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=ROOT,
        text=True,
        check=True,
        capture_output=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def _canonical_module(module: str) -> str:
    return CANONICAL_MODULES.get(module, module)


def _actual_import_pairs() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for path in _tracked_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        relative_path = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in TARGET_MODULES:
                pairs.add((relative_path, _canonical_module(node.module)))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name in TARGET_MODULES:
                        pairs.add((relative_path, _canonical_module(name)))
    return pairs


def _inventory_import_pairs(inventory: dict) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for module, target in inventory["targets"].items():
        for consumer in target["consumers"]:
            pairs.add((consumer["path"], module))
    return pairs


def test_importer_inventory_matches_current_python_imports() -> None:
    inventory = _load_yaml(INVENTORY_PATH)

    assert inventory["contract_version"] == 1
    assert _inventory_import_pairs(inventory) == _actual_import_pairs()


def test_importer_inventory_classifies_every_consumer_boundary() -> None:
    inventory = _load_yaml(INVENTORY_PATH)

    for module, target in inventory["targets"].items():
        assert target["boundary"] in ALLOWED_BOUNDARIES, module
        assert target["consumers"], module
        for consumer in target["consumers"]:
            assert consumer["boundary"] in ALLOWED_BOUNDARIES, consumer


@pytest.mark.parametrize("vector", _load_yaml(VECTORS_PATH)["transport_reconstruction"]["vectors"])
def test_transport_reconstruction_vectors(vector: dict) -> None:
    assert build_transport_url(vector["input"], vector["backend_port"]) == vector["expect"]


@pytest.mark.parametrize("vector", _load_yaml(VECTORS_PATH)["model_endpoint_allow_deny"]["vectors"])
def test_model_endpoint_allow_deny_vectors(vector: dict) -> None:
    if vector.get("expect_error") == "ModelEndpointPolicyError":
        with pytest.raises(ModelEndpointPolicyError):
            validate_model_endpoint_url(vector["input"], allow_public=vector["allow_public"])
    else:
        assert validate_model_endpoint_url(
            vector["input"],
            allow_public=vector["allow_public"],
        ) == vector["expect"]


def test_behavior_vectors_declare_contract_and_keep_redirects_out_of_transport() -> None:
    vectors = _load_yaml(VECTORS_PATH)

    assert vectors["contract_version"] == 1
    for vector in vectors["transport_reconstruction"]["vectors"]:
        assert "redirect" not in vector["id"]


def test_contract_declares_single_transport_authority_and_distinct_boundaries() -> None:
    contract = _load_yaml(CONTRACT_PATH)

    assert contract["transport_reconstruction"]["executable_authority"] == (
        "src/utils/endpoint_policy_core.py"
    )
    assert contract["transport_reconstruction"]["executable_authorities"] == [
        "src/utils/endpoint_policy_core.py"
    ]
    assert contract["model_endpoint_validation"]["authority"] == (
        "src/utils/model_endpoint_url.py"
    )
    assert contract["ssrf_layers"]["preflight_authority"] == "src/utils/ssrf_fetch_policy.py"
    assert contract["ssrf_layers"]["pinned_transport_authority"] == (
        "src/utils/ssrf_pinned_adapter.py"
    )
    assert "transport compatibility adapter" not in str(contract).lower()
