"""Tests for Layer-3 Kubernetes & CNI egress policy manifests."""
from __future__ import annotations

from pathlib import Path
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "deploy" / "k8s" / "egress-policies"


class TestK8sEgressManifests:
    """Test suite for declarative Kubernetes and CNI egress policy manifests."""

    def test_manifests_exist(self) -> None:
        assert (K8S_DIR / "cilium-egress-metadata-deny.yaml").exists()
        assert (K8S_DIR / "calico-egress-global-deny.yaml").exists()
        assert (K8S_DIR / "k8s-network-policy-baseline.yaml").exists()
        assert (K8S_DIR / "README.md").exists()

    def test_cilium_manifest_structure_and_cidrs(self) -> None:
        content = (K8S_DIR / "cilium-egress-metadata-deny.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert data["apiVersion"] == "cilium.io/v2"
        assert data["kind"] == "CiliumNetworkPolicy"
        assert data["metadata"]["name"] == "perpetua-agent-egress-deny-metadata"

        # Verify egressDeny contains all cloud metadata and link-local CIDRs
        egress_deny = data["spec"]["egressDeny"]
        cidrs = [item["cidr"] for rule in egress_deny for item in rule.get("toCIDRSet", [])]
        assert "169.254.169.254/32" in cidrs
        assert "169.254.0.0/16" in cidrs
        assert "fd00:ec2::254/128" in cidrs
        assert "fe80::/10" in cidrs

    def test_calico_manifest_structure_and_nets(self) -> None:
        content = (K8S_DIR / "calico-egress-global-deny.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert data["apiVersion"] == "projectcalico.org/v3"
        assert data["kind"] == "GlobalNetworkPolicy"

        # Verify deny rule contains all metadata nets
        deny_rules = [r for r in data["spec"]["egress"] if r.get("action") == "Deny"]
        assert len(deny_rules) >= 1
        nets = deny_rules[0]["destination"]["nets"]
        assert "169.254.169.254/32" in nets
        assert "169.254.0.0/16" in nets
        assert "fd00:ec2::254/128" in nets
        assert "fe80::/10" in nets

    def test_baseline_k8s_network_policy_structure(self) -> None:
        content = (K8S_DIR / "k8s-network-policy-baseline.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert data["apiVersion"] == "networking.k8s.io/v1"
        assert data["kind"] == "NetworkPolicy"
        assert "Egress" in data["spec"]["policyTypes"]
