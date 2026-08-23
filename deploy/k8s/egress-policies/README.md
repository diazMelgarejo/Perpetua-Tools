# Layer-3 Egress Security Policies (Kubernetes & CNI Profile)

This directory contains declarative Layer-3 egress firewall policies for containerized
and Kubernetes deployments of Perpetua-Tools / orama-system agent workers.

## Architectural Context

In the primary local environment (macOS + Windows LAN), Layer-3 egress enforcement is
handled directly by the host OS:

- **macOS:** `/etc/pf.anchors/com.perpetua-tools.egress-deny` via
  `scripts/security/install-egress-pf-rules.sh`.
- **Windows:** Windows Defender Firewall outbound rules for LM Studio / AutoResearchers.

For containerized and Kubernetes cluster deployments, use the manifests in this
directory to enforce an identical Layer-3 defense-in-depth floor beneath Layer 1/2
application SSRF policies (`SSRFPinnedHTTPAdapter`).

## The Kubernetes NetworkPolicy Additive Trap

Standard Kubernetes `NetworkPolicy` objects are **strictly additive**. If an existing
broad allow policy selects the same pods, a narrower policy cannot subtract
permissions. Therefore:

1. **Cilium (`cilium-egress-metadata-deny.yaml`):** Uses native `CiliumNetworkPolicy`
   `egressDeny` to enforce hard fail-closed drops regardless of any coexisting allow
   rules.
2. **Calico (`calico-egress-global-deny.yaml`):** Uses Calico `GlobalNetworkPolicy`
   with explicit `action: Deny` evaluated before allow rules.
3. **Standard K8s (`k8s-network-policy-baseline.yaml`):** Uses `ipBlock.except` for
   standard vanilla clusters where advanced CNI CRDs are unavailable.

## Applying Policies

```bash
# For Cilium CNI:
kubectl apply -f cilium-egress-metadata-deny.yaml

# For Calico CNI:
kubectl apply -f calico-egress-global-deny.yaml

# For Vanilla Kubernetes NetworkPolicy:
kubectl apply -f k8s-network-policy-baseline.yaml
```
