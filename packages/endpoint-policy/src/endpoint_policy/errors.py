"""The single typed error the endpoint policy layer may raise."""
from __future__ import annotations


class ModelEndpointPolicyError(ValueError):
    """Raised when a model endpoint URL violates egress policy."""
