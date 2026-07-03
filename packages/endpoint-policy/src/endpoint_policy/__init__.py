"""perpetua-endpoint-policy — shared endpoint/URL egress policy.

Invariant: a model endpoint is either a valid, normalized string, or a single
``ModelEndpointPolicyError``. No raw URL-parsing exception escapes this layer.
"""
from ._version import __version__
from .errors import ModelEndpointPolicyError
from .hosts import host_allowed, redact_endpoint_for_log
from .validator import (
    allow_public_model_endpoints,
    parse_model_endpoint_list,
    validate_model_endpoint_url,
)

__all__ = [
    "__version__",
    "ModelEndpointPolicyError",
    "allow_public_model_endpoints",
    "host_allowed",
    "parse_model_endpoint_list",
    "redact_endpoint_for_log",
    "validate_model_endpoint_url",
]
