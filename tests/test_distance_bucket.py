"""
tests/test_distance_bucket.py — Tests for Kademlia-style peer ID distance bucketing (G6).

Coverage:
- SHA256-derived integer keys are deterministic and distinct for different inputs
- XOR distance is symmetric and zero for identical peer IDs
- KBucketTable places peers in buckets by XOR distance from a local ID
- KBucketTable enforces the k-cap per bucket with LRU eviction
- is_correlated() flags peers that are close in ID-space and rejects distant peers
"""

from unittest.mock import patch

import pytest

from orchestrator.distance_bucket import (
    KBucketTable,
    peer_id_to_int,
    xor_distance,
)


class TestPeerIdToInt:
    """SHA256 canonicalization of arbitrary peer ID strings."""

    def test_peer_id_to_int_is_deterministic(self):
        """The same string must always map to the same 256-bit key."""
        key1 = peer_id_to_int("alice-node.example.com")
        key2 = peer_id_to_int("alice-node.example.com")
        assert key1 == key2

    def test_different_peer_ids_usually_differ(self):
        """Distinct strings must not collide in the hashed keyspace."""
        a = peer_id_to_int("peer-alpha-12345")
        b = peer_id_to_int("peer-beta-67890")
        assert a != b

    def test_peer_id_to_int_is_fixed_width(self):
        """The output must fit in the SHA256 256-bit keyspace."""
        key = peer_id_to_int("any-string")
        assert isinstance(key, int)
        assert 0 <= key < 2**256


class TestXorDistance:
    """Kademlia XOR metric properties."""

    def test_xor_distance_is_symmetric(self):
        """d(a, b) must equal d(b, a)."""
        a, b = "node-a", "node-b"
        assert xor_distance(a, b) == xor_distance(b, a)

    def test_xor_distance_self_is_zero(self):
        """d(a, a) must be zero."""
        assert xor_distance("node-a", "node-a") == 0

    def test_xor_distance_distinct_is_positive(self):
        """Different peer IDs must have a positive XOR distance."""
        assert xor_distance("node-a", "node-b") > 0


class TestKBucketTable:
    """K-bucket insertion, ordering, and eviction."""

    def _find_peers_in_bucket(
        self, table: KBucketTable, needed: int, max_candidates: int = 20000
    ) -> tuple[int, list[str]]:
        """Return ``needed`` distinct probe IDs that fall into the same bucket."""
        peers: list[str] = []
        target_bucket: int | None = None
        for i in range(max_candidates):
            candidate = f"probe-{i:05d}"
            bucket = table.bucket_for(candidate)
            if target_bucket is None:
                target_bucket = bucket
            if bucket == target_bucket:
                peers.append(candidate)
            if len(peers) == needed:
                return target_bucket, peers
        raise AssertionError(
            f"could not find {needed} peers in the same bucket "
            f"(last bucket: {target_bucket}, found: {len(peers)})"
        )

    def test_bucket_for_local_id_is_zero(self):
        """The local ID itself sits in bucket 0 (zero distance)."""
        table = KBucketTable("local-peer")
        assert table.bucket_for("local-peer") == 0

    def test_update_buckets_by_actual_distance(self):
        """Peers are placed in the bucket matching their XOR distance magnitude."""
        table = KBucketTable("local-peer", k=10)
        target_bucket, peers = self._find_peers_in_bucket(table, 5)

        for idx, peer in enumerate(peers):
            table.update(peer, float(idx))

        # All inserted peers should be in the same bucket.
        assert set(table.peers_in_bucket(target_bucket)) == set(peers)
        assert table.bucket_for(peers[0]) == target_bucket

    def test_update_respects_k_cap_and_evicts_oldest(self):
        """A bucket holds at most k entries, evicting the oldest on overflow."""
        table = KBucketTable("local-peer", k=3)
        target_bucket, peers = self._find_peers_in_bucket(table, 5)

        for idx, peer in enumerate(peers):
            table.update(peer, float(idx))

        stored = table.peers_in_bucket(target_bucket)
        # Most-recent-last ordering: the oldest two entries should be evicted.
        assert stored == peers[-3:]
        assert len(stored) == 3

    def test_update_moves_existing_peer_to_most_recent(self):
        """Updating a peer already in a bucket refreshes it to the tail."""
        table = KBucketTable("local-peer", k=3)
        target_bucket, peers = self._find_peers_in_bucket(table, 2)
        peer_a, peer_b = peers

        table.update(peer_a, 1.0)
        table.update(peer_b, 2.0)
        table.update(peer_a, 3.0)

        assert table.peers_in_bucket(target_bucket) == [peer_b, peer_a]


class TestIsCorrelated:
    """ID-space proximity detection for Sybil correlation."""

    def _fake_key(self, peer_id: str) -> int:
        """Controllable keyspace mapping for correlation tests.

        Sequential ``seq-N`` IDs map directly to integer N so their XOR distance
        is small and predictable; other strings fall back to a stable hash.
        """
        if peer_id.startswith("seq-"):
            return int(peer_id.split("-", 1)[1])
        return peer_id_to_int(peer_id)

    def test_correlated_for_close_ids(self):
        """Sequential IDs that are close in keyspace are flagged as correlated."""
        with patch(
            "orchestrator.distance_bucket.peer_id_to_int", side_effect=self._fake_key
        ):
            table = KBucketTable("local-peer")
            assert table.is_correlated("seq-1", "seq-2") is True
            assert table.is_correlated("seq-10", "seq-11") is True
            # xor_distance(0, 15) == 15 -> bit_length == 4, at the default threshold.
            assert table.is_correlated("seq-0", "seq-15") is True

    def test_not_correlated_for_distant_ids(self):
        """Peers far apart in ID-space are not flagged with the default threshold."""
        with patch(
            "orchestrator.distance_bucket.peer_id_to_int", side_effect=self._fake_key
        ):
            table = KBucketTable("local-peer")
            assert table.is_correlated("seq-0", "seq-100") is False
            assert table.is_correlated("seq-0", "seq-1000") is False

    def test_self_is_always_correlated(self):
        """A peer is trivially at zero distance from itself."""
        table = KBucketTable("local-peer")
        assert table.is_correlated("any-peer-id", "any-peer-id") is True

    def test_correlation_threshold_is_configurable(self):
        """A larger proximity threshold accepts more distant peers."""
        with patch(
            "orchestrator.distance_bucket.peer_id_to_int", side_effect=self._fake_key
        ):
            table = KBucketTable("local-peer")
            # seq-0 and seq-100 are 7 bits apart, above default 4.
            assert table.is_correlated("seq-0", "seq-100", proximity_bits=4) is False
            assert table.is_correlated("seq-0", "seq-100", proximity_bits=8) is True
