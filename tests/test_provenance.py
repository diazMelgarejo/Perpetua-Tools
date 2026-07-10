"""
tests/test_provenance.py — Tests for subnet-aware provenance bucketing (G1).

Coverage:
- IPv4 addresses on the same /24 collapse to one bucket
- IPv4 addresses on different /24s bucket separately
- IPv6 addresses on the same /64 collapse to one bucket
- Opaque non-IP labels pass through unchanged
- Malformed or empty input does not raise
"""

import pytest

from orchestrator.provenance import provenance_bucket


class TestProvenanceBucketIPv4:
    """IPv4 address and CIDR bucketing."""

    def test_same_ipv4_subnet_buckets_together(self):
        """Two IPs in the same /24 collapse to the same provenance bucket."""
        bucket_a = provenance_bucket("192.168.1.10")
        bucket_b = provenance_bucket("192.168.1.50")
        assert bucket_a == bucket_b == "192.168.1.0/24"

    def test_different_ipv4_subnets_bucket_separately(self):
        """IPs in different /24s produce distinct provenance buckets."""
        bucket_a = provenance_bucket("192.168.1.10")
        bucket_b = provenance_bucket("192.168.2.10")
        assert bucket_a != bucket_b
        assert bucket_a == "192.168.1.0/24"
        assert bucket_b == "192.168.2.0/24"

    def test_ipv4_cidr_collapses_to_slash24(self):
        """A wider or narrower IPv4 CIDR is normalized to its /24 bucket."""
        assert provenance_bucket("192.168.1.0/24") == "192.168.1.0/24"
        assert provenance_bucket("192.168.1.128/25") == "192.168.1.0/24"
        assert provenance_bucket("10.0.0.0/8") == "10.0.0.0/24"


class TestProvenanceBucketIPv6:
    """IPv6 address and CIDR bucketing."""

    def test_same_ipv6_subnet_buckets_together(self):
        """Two IPs in the same /64 collapse to the same provenance bucket."""
        bucket_a = provenance_bucket("2001:db8::1")
        bucket_b = provenance_bucket("2001:db8::ffff")
        assert bucket_a == bucket_b == "2001:db8::/64"

    def test_different_ipv6_subnets_bucket_separately(self):
        """IPs in different /64s produce distinct provenance buckets."""
        bucket_a = provenance_bucket("2001:db8::1")
        bucket_b = provenance_bucket("2001:db8:1::1")
        assert bucket_a != bucket_b

    def test_ipv6_cidr_collapses_to_slash64(self):
        """A wider or narrower IPv6 CIDR is normalized to its /64 bucket."""
        assert provenance_bucket("2001:db8::/64") == "2001:db8::/64"
        assert provenance_bucket("2001:db8::/128") == "2001:db8::/64"
        assert provenance_bucket("2001::/32") == "2001::/64"


class TestProvenanceBucketOpaque:
    """Opaque non-IP provenance labels."""

    def test_opaque_labels_pass_through_unchanged(self):
        """ASN strings and other opaque labels are returned literally."""
        assert provenance_bucket("ASN-12345") == "ASN-12345"
        assert provenance_bucket("my-custom-origin") == "my-custom-origin"
        assert provenance_bucket("") == ""


class TestProvenanceBucketMalformed:
    """Malformed inputs must not raise."""

    def test_malformed_ip_does_not_raise(self):
        """Garbage that looks like an invalid IP returns the original string."""
        assert provenance_bucket("not-an-ip") == "not-an-ip"
        assert provenance_bucket("192.168.1") == "192.168.1"
        assert provenance_bucket("999.999.999.999") == "999.999.999.999"
        assert provenance_bucket("::gibberish") == "::gibberish"
