"""Shared provenance helpers for episodic entries. Cached per-process."""
import os, subprocess, uuid

AGENT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_CACHED_COMMIT = None
_CACHED_RUN_ID = None
_CACHED_PROFILE = None


def run_id():
    """Return this process's run id: ``AGENT_RUN_ID``, else a cached opaque ``run-<12 hex>``."""
    global _CACHED_RUN_ID
    if _CACHED_RUN_ID is None:
        # Opaque per-process fallback: a pid is reused across runs and leaks host detail.
        _CACHED_RUN_ID = os.environ.get("AGENT_RUN_ID") or f"run-{uuid.uuid4().hex[:12]}"
    return _CACHED_RUN_ID


def profile():
    """Return the active harness profile name, or "default" when unknown.

    Harnesses that run multiple isolated agent identities against the same
    portable brain (e.g. Hermes's --profile flag spawning distinct
    specialist agents) should set ``AGENT_PROFILE`` to the active name so
    every episodic entry is tagged. Enables cross-profile clustering and
    per-specialist retrospectives in the dream cycle.

    Fallback detection covers known harnesses without code changes there:
      * ``AGENT_PROFILE``  - canonical, any harness.
      * ``HERMES_HOME``    - if it points under ``<...>/profiles/<name>``
                             use that name; otherwise "default".
    """
    global _CACHED_PROFILE
    if _CACHED_PROFILE is not None:
        return _CACHED_PROFILE

    explicit = os.environ.get("AGENT_PROFILE", "").strip()
    if explicit:
        _CACHED_PROFILE = explicit
        return _CACHED_PROFILE

    hermes_home = os.environ.get("HERMES_HOME", "").rstrip("/")
    if hermes_home:
        if "/profiles/" in hermes_home:
            _CACHED_PROFILE = hermes_home.rsplit("/", 1)[-1]
        else:
            _CACHED_PROFILE = "default"
        return _CACHED_PROFILE

    _CACHED_PROFILE = "default"
    return _CACHED_PROFILE


def commit_sha():
    """Return the cached HEAD commit of the agent root, or an empty string without git."""
    global _CACHED_COMMIT
    if _CACHED_COMMIT is None:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=2,
                cwd=AGENT_ROOT,
            )
            _CACHED_COMMIT = out.stdout.strip() if out.returncode == 0 else ""
        except Exception:
            _CACHED_COMMIT = ""
    return _CACHED_COMMIT


def build_source(skill):
    """Return the ``source`` provenance mapping stamped on every episodic entry."""
    return {
        "skill": skill,
        "profile": profile(),
        "run_id": run_id(),
        "commit_sha": commit_sha(),
    }
