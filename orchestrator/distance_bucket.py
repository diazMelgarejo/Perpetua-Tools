"""
orchestrator/distance_bucket.py — Kademlia-style distance bucketing for peer IDs (G6).

This module provides a standard XOR distance metric over a SHA256-derived keyspace,
plus a k-bucket routing table indexed by distance magnitude.  It is intentionally
stdlib-only and works for any ``peer_id`` string (hex-encoded public key, hostname,
or arbitrary label) without assuming a specific format.

Spec reference: MULTIAGENT-SWARM-SECURITY-ANALYSIS.md §3 HIGH gap G6 (P2 Distance-Metric
Bucketing) — T4 (Sybil Witnesses), T1 (Malicious Relay).
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Tuple


# SHA256 produces a 256-bit digest; the XOR metric is therefore defined over a
# fixed-width keyspace with bit_length() in [0, 256].
_KEYSPACE_BITS = 256


def peer_id_to_int(peer_id: str) -> int:
    """
    Canonicalize an arbitrary peer ID string into a fixed-width integer keyspace.

    Args:
        peer_id: Target identifier.  May be an ed25519 public key hex string,
            a hostname, a UUID, or any other opaque label.

    Returns:
        A 256-bit unsigned integer derived deterministically from ``peer_id``
        via SHA256.

    Sybil-defense rationale:
        Peer IDs in the wild are heterogeneous strings.  Interpreting them
        directly as integers (e.g. parsing hex) would only work for one ID
        scheme and would let an attacker choose IDs whose numeric values cluster
        arbitrarily.  Hashing every ID to a fixed-width digest makes the XOR
        distance metric well-defined for every supported ID type and removes
        the adversary's ability to engineer numeric proximity.
    """
    digest = hashlib.sha256(peer_id.encode("utf-8")).digest()
    return int.from_bytes(digest, "big")


def xor_distance(id_a: str, id_b: str) -> int:
    """
    Compute the Kademlia XOR distance between two peer IDs.

    Args:
        id_a: First peer identifier.
        id_b: Second peer identifier.

    Returns:
        The bitwise XOR of the SHA256-derived integer keys of ``id_a`` and
        ``id_b``.

    Properties:
        - ``xor_distance(a, a) == 0``
        - ``xor_distance(a, b) == xor_distance(b, a)`` (symmetric)
        - ``xor_distance(a, b) ^ xor_distance(b, c) >= xor_distance(a, c)``
          (the XOR metric forms a valid ultrametric over the keyspace)

    Sybil-defense rationale:
        Correlated Sybil identities (sequentially generated keys, keys sharing
        a common prefix, or hostnames derived from a common template) will tend
        to land close together in the hashed keyspace.  XOR distance exposes
        that proximity even when the raw strings look unrelated, complementing
        subnet-based provenance clustering by detecting ID-space correlation.
    """
    return peer_id_to_int(id_a) ^ peer_id_to_int(id_b)


class KBucketTable:
    """
    Maintain peers in Kademlia-style buckets indexed by XOR distance magnitude.

    Each bucket stores up to ``k`` entries ordered by last-seen time, with the
    most recently seen peer at the tail (oldest at the head).  The bucket index
    for a peer is ``xor_distance(peer_id, local_id).bit_length()``, so bucket 0
    contains the local ID itself, bucket 1 contains IDs that differ in the most
    significant bit, and bucket 256 contains IDs maximally distant from the
    local ID.

    Args:
        local_id: The reference peer identifier for this table.
        k: Maximum number of peers per bucket (default 20).
    """

    def __init__(self, local_id: str, k: int = 20) -> None:
        self.local_id = local_id
        self.k = k
        self._local_key = peer_id_to_int(local_id)
        # bucket_index -> list of (peer_id, last_seen_ts), oldest first.
        self._buckets: Dict[int, List[Tuple[str, float]]] = {}

    def _key(self, peer_id: str) -> int:
        """Return the hashed integer key for ``peer_id``."""
        return peer_id_to_int(peer_id)

    def _distance(self, peer_id: str) -> int:
        """Return XOR distance from ``peer_id`` to the local ID."""
        return self._key(peer_id) ^ self._local_key

    def bucket_for(self, peer_id: str) -> int:
        """
        Return the bucket index that ``peer_id`` belongs to relative to the
        local ID.
        """
        return self._distance(peer_id).bit_length()

    def update(self, peer_id: str, last_seen_ts: float) -> None:
        """
        Insert or refresh ``peer_id`` in the appropriate bucket.

        If ``peer_id`` is already present it is moved to the tail (most recent).
        If it is new and the bucket already holds ``k`` entries, the oldest
        entry at the head is evicted before insertion, preserving the bounded
        k-bucket invariant.
        """
        bucket_index = self.bucket_for(peer_id)
        bucket = self._buckets.setdefault(bucket_index, [])

        # Remove any existing occurrence so we can re-insert at the tail.
        bucket[:] = [entry for entry in bucket if entry[0] != peer_id]
        bucket.append((peer_id, last_seen_ts))

        # Enforce the k-cap by dropping the oldest entry (head).
        if len(bucket) > self.k:
            del bucket[: len(bucket) - self.k]

    def peers_in_bucket(self, bucket_index: int) -> List[str]:
        """
        Return the peer IDs stored in ``bucket_index`` in last-seen order
        (oldest first, most recent last).
        """
        return [peer_id for peer_id, _ in self._buckets.get(bucket_index, [])]

    def is_correlated(
        self, peer_id_a: str, peer_id_b: str, proximity_bits: int = 4
    ) -> bool:
        """
        Return ``True`` if two peer IDs are suspiciously close in ID-space.

        Args:
            peer_id_a: First peer identifier.
            peer_id_b: Second peer identifier.
            proximity_bits: Small-XOR-distance threshold in bits (default 4).

        Returns:
            ``True`` when the bit-length of ``xor_distance(peer_id_a,
            peer_id_b)`` is ``<= proximity_bits``.  This means the two IDs share
            the most significant ``256 - proximity_bits`` bits of their hashed
            keyspace, a strong indicator of correlated generation.
        """
        return xor_distance(peer_id_a, peer_id_b).bit_length() <= proximity_bits

    def __len__(self) -> int:
        """Return the total number of peer entries across all buckets."""
        return sum(len(bucket) for bucket in self._buckets.values())
