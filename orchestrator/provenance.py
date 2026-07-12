"""
orchestrator/provenance.py — Provenance bucketing for Sybil-defense witness quorum (G1).

This module classifies ``observer_provenance`` values into comparable network buckets
using only the Python stdlib ``ipaddress`` module.  IPv4 and IPv6 addresses (and
CIDRs) are collapsed to their containing /24 (IPv4) or /64 (IPv6) network; opaque
labels are returned unchanged so they remain comparable by literal equality.

Spec reference: D4 § T4 (Sybil Witnesses) + D1 § 3 (witness_multiplier)
"""

import ipaddress


def provenance_bucket(provenance: str) -> str:
    """
    Classify an observer_provenance value into a comparable provenance bucket.

    Args:
        provenance: Network origin identifier.  May be an IPv4 address, IPv6
            address, CIDR prefix, or opaque label (e.g., ASN string, empty
            unknown marker).

    Returns:
        A canonical bucket string.  For IPv4 this is the containing /24 network
        (e.g., ``127.0.1.0/24``); for IPv6 this is the containing /64 network
        (e.g., ``2001:db8::/64``); for non-IP strings this is the original
        literal value.

    Sybil-defense rationale:
        Raw provenance strings are trivially spoofable: an attacker running
        multiple identities on the same subnet can provide a different arbitrary
        provenance string per identity and appear to originate from independent
        network origins.  Bucketing by subnet collapses those identities to a
        single provenance unit, so the witness quorum gate counts independent
        networks rather than self-reported labels.
    """
    if not provenance:
        return provenance

    try:
        network = ipaddress.ip_network(provenance, strict=False)
    except ValueError:
        # Opaque label (ASN, unknown marker, malformed input, etc.)
        return provenance

    if isinstance(network, ipaddress.IPv4Network):
        bucket_prefix = 24
    elif isinstance(network, ipaddress.IPv6Network):
        bucket_prefix = 64
    else:
        return provenance

    # Collapse to the containing subnet of the bucket size.
    bucket = ipaddress.ip_network((network.network_address, bucket_prefix), strict=False)
    return str(bucket)
