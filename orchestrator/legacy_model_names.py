"""Retired GLM model names and their replacements, for operator overrides that still use the old names.

Operators may set ``PIPELINE_<ALIAS>_MODEL`` or ``MAC_MANAGER_MODEL`` to a model name. When the registry
renamed ``glm-5.1:cloud`` / ``glm-5.1`` / ``glm-5.2`` to ``glm-5.3-flash``, an existing override with the
old name would stop resolving (a pipeline override fails validation; a manager override silently falls
through to another model). This module maps the retired names forward and says so in the log.
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

LEGACY_MODEL_NAMES: dict[str, str] = {
    "glm-5.1:cloud": "glm-5.3-flash:cloud",
    "glm-5.1": "glm-5.3-flash",
    "glm-5.2": "glm-5.3-flash",
}


def canonical_model_name(name: str, source: str = "") -> str:
    """Return *name* mapped to its current model name when it is a retired GLM name.

    Matching ignores case and surrounding whitespace. A mapped name logs a deprecation warning that
    names *source* (for example the environment variable); any other name, including an empty one,
    is returned unchanged so the caller's normal validation still applies.
    """
    replacement = LEGACY_MODEL_NAMES.get(name.strip().lower())
    if replacement is None:
        return name
    _log.warning(
        "%s names the retired model %r; using %r. Update the override to the current name.",
        source or "model override", name.strip(), replacement,
    )
    return replacement
