"""orchestrator/autoresearch_bridge.py

Layer 4 integration: autoresearch as a managed foot-soldier.

Architecture (post-migration)
------------------------------
`/autoresearch` slash command UX, no single hard dependency -- 3-tier fallback:
  1. Global skill/command install (idempotent, filesystem-only check) --
     `scripts/install-vendor-guided.sh` / `vendor/autoresearch/scripts/install.sh
     --claude --global`, landing at ~/.claude/skills/autoresearch +
     ~/.claude/commands/autoresearch*. Preferred: no subprocess, no network.
  2. Claude Code plugin marketplace -- `claude plugin marketplace add
     uditgoenka/autoresearch` + `claude plugin install autoresearch@autoresearch`.
     Best-effort; any failure (missing `claude` binary, timeout, non-zero exit)
     degrades instead of raising.
  3. Micro-implementation fallback -- neither tier above is required for the
     actual orchestration in this module (git sync, GPU dispatch, dry-run
     planning); only the slash-command UX needs tier 1 or 2. See
     `install_autoresearch_plugin()`.
Any tier -> can execute anywhere (Mac, Windows, CI) without SSH.

Secondary mode: When task_type is `ml-experiment`, the GPU runner at $GPU_BOX
                is used as an optional `Verify` substrate via SSH, reading
                swarm_state.md for GPU locks. This path is NOT removed; it
                becomes the dedicated hardware verifier for ML experiments.

Planning mode: dry-run orchestration plans classify a plain-language goal using
               the upstream uditgoenka/autoresearch archetypes and return the
               predicate, pipeline, state snapshot, and safety gates without
               invoking Claude, plugin install, git sync, SSH, SCP, LM Studio,
               or GPU work.

Responsibilities
----------------
- Idempotent git sync of the canonical autoresearch clone on the Windows GPU runner.
- Spawning the three cognitive swarm agents (Coder, Evaluator, Orchestrator) via
  the top-level Perpetua-Tools AgentTracker so lifecycle and idempotency are
  consistent with the rest of the stack.
- Reading swarm_state.md for GPU lock status before dispatching any training run.
- Making the `/autoresearch` slash command available idempotently, preferring
  the global skill install over the Claude Code plugin marketplace, and never
  hard-failing if neither is present (see `install_autoresearch_plugin`).
- Preparing dry-run plans that pass only state + goal/archetype metadata to the
  higher-level Perpetua/orama orchestrator path.

Design rules (from approved interoperability contract)
------------------------------------------------------
1. ONLY Perpetua-Tools/orchestrator.py (or the FastAPI /autoresearch/* endpoints)
   may call sync_autoresearch_idempotent(). Layers 2-4 treat autoresearch as
   read-only from a lifecycle perspective.
2. The autoresearch clone lives in ONE canonical path on the Windows GPU runner:
       C:/Users/<WINUSER>/autoresearch/
   Never duplicate it.
3. File transfer uses scp only (rsync not guaranteed on Windows SSH sessions).
4. API keys are NEVER written to files; they are injected as session env vars.
5. GPU lock is the IDLE/BUSY flag in swarm_state.md: no external queue daemon.
6. Windows model loading is STRICTLY SEQUENTIAL: never dispatch a new GPU run
   while swarm_state.md shows GPU: BUSY.
7. Long-running goals MUST start with dry-run planning. Dry-run never executes
   Claude/plugin/GPU/network substrate actions.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import textwrap
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from utils.model_endpoint_url import ModelEndpointPolicyError, validate_model_endpoint_url

# -- configuration (resolved from environment, never hard-coded secrets) --------

# GPU_BOX: SSH target for the Windows RTX 3080.
# Uses detect_active_tilting_ip() host if GPU_BOX not set, but SSH needs user@host
# so we keep a separate env var. No fabricated default: an unset GPU_BOX must
# fail closed (ssh to an empty target errors immediately and clearly) rather
# than silently resolving to 192.0.2.1 — a TEST-NET-1 documentation address
# that looks like a real host but never routes anywhere. Callers should either
# set GPU_BOX explicitly or use the existing use_http_local_preflight() path.
GPU_BOX: str = os.environ.get("GPU_BOX", "")
GPU_REPO_PATH: str = os.environ.get("GPU_REPO_PATH", "autoresearch")

# Primary: uditgoenka/autoresearch Claude Code plugin (env-var configurable).
# The tracked vendor/autoresearch submodule is a source/reference mirror; runtime
# still installs the plugin and may sync LOCAL_AUTORESEARCH_PATH/GPU_REPO_PATH.
AUTORESEARCH_REMOTE: str = os.environ.get(
    "AUTORESEARCH_REMOTE", "https://github.com/uditgoenka/autoresearch.git"
)
AUTORESEARCH_DEFAULT_BRANCH: str = os.environ.get("AUTORESEARCH_BRANCH", "master")
AUTORESEARCH_UPSTREAM_PRIMARY: str = "https://github.com/uditgoenka/autoresearch"
AUTORESEARCH_UPSTREAM_PRIMARY_PIN: str = "9f51f726e513be4e899b6afeed9f9c55fc1f51f3"
AUTORESEARCH_UPSTREAM_SECONDARY: str = "https://github.com/karpathy/autoresearch"
AUTORESEARCH_UPSTREAM_SECONDARY_PIN: str = "c92bee55ebc339e8b1501f6b5c9cfb54835a9de8"

SSH_TIMEOUT: int = int(os.environ.get("SSH_TIMEOUT", "90"))
DEFAULT_MAX_CYCLES: int = int(os.environ.get("AUTORESEARCH_MAX_CYCLES", "50"))

# HTTP-local preflight (Win operator on GPU host: skip SSH, probe LM Studio).
# auto | http-local | ssh
AUTORESEARCH_PREFLIGHT_MODE: str = os.environ.get(
    "AUTORESEARCH_PREFLIGHT_MODE", "auto"
).strip().lower()
LM_STUDIO_PROBE_TIMEOUT: int = int(os.environ.get("LM_STUDIO_PROBE_TIMEOUT", "10"))

# WIN_SSH_KEY is the canonical name; DELL_SSH_KEY kept for backward-compat with
# existing .env files from before the subnet rename.
_SSH_KEY: str = os.environ.get("WIN_SSH_KEY") or os.environ.get("DELL_SSH_KEY", "")
_SSH_OPTS: list[str] = (
    ["-i", _SSH_KEY, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
    if _SSH_KEY else
    ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
)

# -- Hardware Overload Prevention (HOP) -- win-rtx3080:1234 slot lock ----------
_WIN_LM_STUDIO_SLOT: threading.Lock = threading.Lock()
SLOT_ACQUIRE_TIMEOUT_SECS: int = int(os.environ.get("HOP_SLOT_TIMEOUT", "120"))
CRASH_RECOVERY_SECS: int = 30

LOCAL_REPO_PATH: Path = Path(
    os.environ.get("LOCAL_AUTORESEARCH_PATH", str(Path.home() / "autoresearch"))
)
SWARM_STATE_FILE: Path = LOCAL_REPO_PATH / "swarm_state.md"

# Upstream v2.2 orchestrator archetypes. Keep these names aligned with
# uditgoenka/autoresearch guide/autoresearch-orchestrator.md.
LOOP_ARCHETYPES = frozenset({
    "fix-broken",
    "ship-ready",
    "optimize-metric",
    "harden",
    "build-feature",
})
SINGLE_PASS_ARCHETYPES = frozenset({
    "explore",
    "document",
    "decide-design",
    "what-to-build",
})

PIPELINES: dict[str, list[str]] = {
    "fix-broken": ["debug", "fix", "regression"],
    "ship-ready": ["regression", "fix", "ship"],
    "optimize-metric": ["plan", "core-loop"],
    "harden": ["security", "fix", "security"],
    "build-feature": ["scenario", "fix", "regression"],
    "explore": ["scenario"],
    "document": ["learn"],
    "decide-design": ["reason"],
    "what-to-build": ["improve"],
}


# -- data types ----------------------------------------------------------------

@dataclass
class SyncResult:
    ok: bool
    sha: str = ""
    error: str = ""


@dataclass
class SwarmState:
    gpu_status: str = "IDLE"       # IDLE | BUSY
    baseline_val_bpb: float = 0.0
    baseline_sha: str = ""
    orchestrator_directive: str = ""
    evaluator_findings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AutoresearchPlan:
    """Side-effect-free orchestration plan for an autoresearch goal."""

    goal: str
    task_type: str
    archetype: str
    mode: str
    predicate: str
    pipeline: list[str]
    max_cycles: int
    dry_run: bool
    units_remaining: str
    ship_requires_approval: bool
    plugin_execution: str
    gpu_execution: str
    orama_methodology: str
    upstream_primary: str
    upstream_secondary: str
    notes: list[str]
    swarm_state: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


# -- progress helper -----------------------------------------------------------

def _progress(label: str, msg: str) -> None:
    """Print a single-line status update (no bar: SSH ops have no duration signal)."""
    print(f"  [{label}] {msg}", flush=True)


# -- dry-run planning ----------------------------------------------------------

def _normalize_goal(goal: str) -> str:
    return " ".join((goal or "").strip().split())


def classify_autoresearch_goal(goal: str, *, task_type: str = "autoresearch") -> str:
    """Classify a goal into the upstream uditgoenka/autoresearch archetypes.

    This is deliberately cheap and deterministic. orama-system may refine the
    classification later, but dry-run must not call paid/cloud tools by default.
    """
    text = _normalize_goal(goal).lower()
    if task_type == "ml-experiment" or any(k in text for k in ("val_bpb", "metric", "optimize", "optimise", "faster", "latency", "benchmark")):
        return "optimize-metric"
    if any(k in text for k in ("harden", "security", "ssrf", "xss", "auth", "token", "vulnerability")):
        return "harden"
    if any(k in text for k in ("ship", "shippable", "production", "release", "deploy")):
        return "ship-ready"
    if any(k in text for k in ("build", "implement", "feature", "tdd", "acceptance")):
        return "build-feature"
    if any(k in text for k in ("bug", "broken", "failing", "failure", "fix", "regression")):
        return "fix-broken"
    if any(k in text for k in ("document", "docs", "readme", "guide")):
        return "document"
    if any(k in text for k in ("decide", "choose", "architecture", "design", "tradeoff")):
        return "decide-design"
    if any(k in text for k in ("what should", "what to build", "roadmap", "opportunity")):
        return "what-to-build"
    return "explore"


def _predicate_for_archetype(archetype: str, *, task_type: str) -> str:
    if task_type == "ml-experiment":
        return "swarm_state.md reports GPU: IDLE and latest log.txt contains a parsed val_bpb"
    if archetype == "fix-broken":
        return "targeted failing test or reproduction command exits 0"
    if archetype == "ship-ready":
        return "configured test + lint + smoke gate exits 0; ship remains HITL-approved"
    if archetype == "optimize-metric":
        return "declared metric improves against baseline without hard regression"
    if archetype == "harden":
        return "security regression tests pass and no HIGH/HARD finding remains open"
    if archetype == "build-feature":
        return "acceptance test count increases and full regression gate remains green"
    if archetype == "document":
        return "requested docs are updated, linked, and repo hygiene passes"
    if archetype == "decide-design":
        return "decision record captures options, tradeoffs, recommendation, and rollback path"
    if archetype == "what-to-build":
        return "ranked opportunity list includes evidence, cost, risk, and next experiment"
    return "single-pass exploration report is produced with findings and next questions"


def _units_for_archetype(archetype: str, *, task_type: str) -> str:
    if task_type == "ml-experiment":
        return "normalized metric delta to target val_bpb"
    if archetype in {"fix-broken", "ship-ready", "harden"}:
        return "failing tests + HARD regressions remaining"
    if archetype == "build-feature":
        return "green acceptance assertions remaining"
    if archetype == "optimize-metric":
        return "normalized metric delta to target"
    return "single-pass: no loop units"


def plan_autoresearch_goal(
    goal: str,
    *,
    task_type: str = "autoresearch",
    max_cycles: Optional[int] = None,
    use_orama: Optional[bool] = None,
) -> AutoresearchPlan:
    """Build an autoresearch dry-run plan without executing substrate actions.

    This is the Perpetua side of `/autoresearch --dry-run`: it passes only the
    goal, upstream archetype, current swarm-state snapshot, and safety gates to
    whichever orchestrator will execute later. It never installs plugins, syncs
    repos, probes LM Studio, or touches the GPU.
    """
    clean_goal = _normalize_goal(goal)
    if not clean_goal:
        clean_goal = "setup autoresearch session"
    archetype = classify_autoresearch_goal(clean_goal, task_type=task_type)
    mode = "orchestration-loop" if archetype in LOOP_ARCHETYPES else "single-pass-dispatch"
    cycles = max_cycles if max_cycles is not None else DEFAULT_MAX_CYCLES
    state = read_swarm_state()
    orama_enabled = bool(use_orama) if use_orama is not None else bool(os.getenv("ORAMA_ENABLED", "").strip())
    notes = [
        "dry-run only: no Claude/plugin/GPU/SSH/SCP/LM Studio calls executed",
        "uditgoenka/autoresearch is primary; karpathy/autoresearch is secondary audit reference",
        "cheapest-first: local policy/deterministic classifier before paid or cloud reasoning",
    ]
    if task_type == "ml-experiment":
        notes.append("GPU verify substrate requires swarm_state.md GPU: IDLE before execution")
    if orama_enabled:
        notes.append("orama-system may refine methodology after this Perpetua state+goal plan")
    return AutoresearchPlan(
        goal=clean_goal,
        task_type=task_type,
        archetype=archetype,
        mode=mode,
        predicate=_predicate_for_archetype(archetype, task_type=task_type),
        pipeline=list(PIPELINES[archetype]),
        max_cycles=cycles,
        dry_run=True,
        units_remaining=_units_for_archetype(archetype, task_type=task_type),
        ship_requires_approval=(archetype == "ship-ready" or "ship" in PIPELINES[archetype]),
        plugin_execution="skipped in dry-run",
        gpu_execution="skipped in dry-run",
        orama_methodology="optional" if orama_enabled else "not requested",
        upstream_primary=f"{AUTORESEARCH_UPSTREAM_PRIMARY}@{AUTORESEARCH_UPSTREAM_PRIMARY_PIN}",
        upstream_secondary=f"{AUTORESEARCH_UPSTREAM_SECONDARY}@{AUTORESEARCH_UPSTREAM_SECONDARY_PIN}",
        notes=notes,
        swarm_state=asdict(state),
    )


# -- locality helpers ----------------------------------------------------------

def _gpu_box_host() -> str:
    """Hostname from GPU_BOX (user@host or bare host)."""
    raw = GPU_BOX.split("@", 1)[-1].strip()
    return raw.split(":", 1)[0].strip().lower()


def _is_loopback_host(host: str) -> bool:
    h = host.strip().lower()
    return h in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _get_local_ips() -> frozenset[str]:
    """Local interface addresses (loopback + LAN) for GPU locality checks."""
    local: set[str] = {"127.0.0.1", "localhost", "::1"}
    try:
        local.add(socket.gethostname().lower())
        for info in socket.getaddrinfo(socket.gethostname(), None):
            local.add(info[4][0])
    except OSError:
        pass
    for probe in ("8.8.8.8", "1.1.1.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.2)
                s.connect((probe, 80))
                local.add(s.getsockname()[0])
                break
        except OSError:
            pass
    return frozenset(local)


def is_gpu_runner_local() -> bool:
    """True when GPU_BOX points at this machine (Win LAN co-orchestration)."""
    host = _gpu_box_host()
    if _is_loopback_host(host):
        return True
    return host in _get_local_ips()


def use_http_local_preflight() -> bool:
    """Whether preflight should skip SSH and use local git + HTTP probes."""
    mode = AUTORESEARCH_PREFLIGHT_MODE
    if mode == "ssh":
        return False
    if mode == "http-local":
        return True
    return is_gpu_runner_local()


def _lm_studio_base_url() -> str:
    """Resolve LM Studio base URL for HTTP preflight (no trailing /v1)."""
    llama = os.environ.get("LLAMA_SERVER_BASE_URL", "").strip()
    if llama:
        parsed = urlparse(llama if "://" in llama else f"http://{llama}")
        base = f"{parsed.scheme}://{parsed.netloc or parsed.path.split('/')[0]}"
        base = base.rstrip("/").removesuffix("/v1")
        try:
            return validate_model_endpoint_url(base)
        except ModelEndpointPolicyError:
            return "http://localhost:1234"
    raw = os.environ.get("LM_STUDIO_WIN_ENDPOINTS", "").strip()
    if raw:
        first = raw.split(",", 1)[0].strip()
        parsed = urlparse(first if "://" in first else f"http://{first}")
        base = f"{parsed.scheme}://{parsed.netloc or parsed.path}".rstrip("/")
        try:
            return validate_model_endpoint_url(base)
        except ModelEndpointPolicyError:
            return "http://localhost:1234"
    return "http://localhost:1234"


def probe_lm_studio_http() -> SyncResult:
    """HTTP GET /v1/models: local GPU readiness without SSH."""
    base = _lm_studio_base_url()
    url = f"{base.rstrip('/')}/v1/models"
    _progress("autoresearch", f"-> Probing LM Studio ({url})...")
    headers: dict[str, str] = {}
    token = os.environ.get("LM_STUDIO_API_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=LM_STUDIO_PROBE_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status >= 400:
                return SyncResult(ok=False, error=f"HTTP {resp.status} from {url}")
            try:
                payload = json.loads(body) if body.strip() else {}
            except json.JSONDecodeError:
                payload = {}
            models = payload.get("data") if isinstance(payload, dict) else None
            count = len(models) if isinstance(models, list) else 0
            _progress("autoresearch", f"OK LM Studio reachable models={count}")
            return SyncResult(ok=True, sha=str(count))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        msg = f"HTTP {exc.code} from {url}: {detail}"
        _progress("autoresearch", f"FAIL {msg}")
        return SyncResult(ok=False, error=msg)
    except Exception as exc:  # noqa: BLE001
        msg = f"LM Studio probe failed ({url}): {exc}"
        _progress("autoresearch", f"FAIL {msg}")
        return SyncResult(ok=False, error=msg)


# -- Claude Code plugin / global skill install ----------------------------------

def _global_autoresearch_install_present() -> bool:
    """Check the idempotent global skill/command install set up by
    scripts/install-vendor-guided.sh (vendor/autoresearch/scripts/install.sh
    --claude --global). Pure filesystem check, no subprocess — checked first
    since it's cheaper and has no external-binary dependency.
    """
    claude_config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or str(Path.home() / ".claude"))
    skill_dir = claude_config_dir / "skills" / "autoresearch"
    command_file = claude_config_dir / "commands" / "autoresearch.md"
    return skill_dir.is_dir() and command_file.is_file()


def install_autoresearch_plugin() -> SyncResult:
    """Make the `/autoresearch` surface available, idempotently, with no hard
    dependency on any single install path.

    Priority:
      1. Global skill/command install already present (see
         `_global_autoresearch_install_present`) -> use it as-is, no subprocess.
      2. Claude Code plugin marketplace (`claude plugin marketplace add/install`)
         -> best-effort; a missing `claude` binary, timeout, or non-zero exit
         degrades instead of raising.
      3. Neither available -> micro-implementation fallback (`ok=True`,
         `sha="micro-fallback"`): the rest of this module's orchestration
         (git sync, GPU dispatch, dry-run planning) does not actually need the
         plugin or global skill installed -- only the `/autoresearch` slash
         command UX does. Callers should treat `sha == "micro-fallback"` as
         "no rich UX, but the pipeline still runs."
    """
    if _global_autoresearch_install_present():
        _progress("autoresearch-plugin", "OK global skill/command install found: using it, skipping plugin marketplace")
        return SyncResult(ok=True, sha="global-skill-install")

    _progress("autoresearch-plugin", "No global skill install found; checking Claude Code plugin marketplace...")
    try:
        list_result = subprocess.run(
            ["claude", "plugin", "list"],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        _progress("autoresearch-plugin", f"claude CLI unavailable ({exc}); falling back to micro-implementation")
        return SyncResult(ok=True, sha="micro-fallback", error=str(exc))

    if list_result.returncode == 0 and "uditgoenka/autoresearch" in list_result.stdout:
        _progress("autoresearch-plugin", "OK plugin already installed: skipping")
        return SyncResult(ok=True, sha="already-installed")

    try:
        _progress("autoresearch-plugin", "-> claude plugin marketplace add uditgoenka/autoresearch")
        add_result = subprocess.run(
            ["claude", "plugin", "marketplace", "add", "uditgoenka/autoresearch"],
            capture_output=True, text=True, timeout=60,
        )
        if add_result.returncode != 0:
            err = f"marketplace add failed: {add_result.stderr.strip()}"
            _progress("autoresearch-plugin", f"{err}; falling back to micro-implementation")
            return SyncResult(ok=True, sha="micro-fallback", error=err)

        _progress("autoresearch-plugin", "-> claude plugin install autoresearch@autoresearch")
        install_result = subprocess.run(
            ["claude", "plugin", "install", "autoresearch@autoresearch"],
            capture_output=True, text=True, timeout=60,
        )
        if install_result.returncode != 0:
            err = f"plugin install failed: {install_result.stderr.strip()}"
            _progress("autoresearch-plugin", f"{err}; falling back to micro-implementation")
            return SyncResult(ok=True, sha="micro-fallback", error=err)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        _progress("autoresearch-plugin", f"plugin install errored ({exc}); falling back to micro-implementation")
        return SyncResult(ok=True, sha="micro-fallback", error=str(exc))

    _progress("autoresearch-plugin", "OK uditgoenka/autoresearch plugin installed")
    return SyncResult(ok=True)


# -- idempotent sync (called by orchestrator before EVERY autoresearch run) -----

def sync_autoresearch_local() -> SyncResult:
    """Pull latest autoresearch in LOCAL_REPO_PATH (no SSH)."""
    repo = LOCAL_REPO_PATH
    _progress("autoresearch", f"-> Syncing locally ({repo})...")
    if not (repo / ".git").is_dir():
        return SyncResult(ok=False, error=f"no git repo at {repo}")
    try:
        fetch = subprocess.run(
            ["git", "-C", str(repo), "fetch", "origin"],
            capture_output=True, text=True, timeout=SSH_TIMEOUT,
        )
        if fetch.returncode != 0:
            err = fetch.stderr.strip() or fetch.stdout.strip()
            _progress("autoresearch", f"FAIL local fetch failed: {err}")
            return SyncResult(ok=False, error=err)
        reset = subprocess.run(
            ["git", "-C", str(repo), "reset", "--hard", f"origin/{AUTORESEARCH_DEFAULT_BRANCH}"],
            capture_output=True, text=True, timeout=SSH_TIMEOUT,
        )
        if reset.returncode != 0:
            err = reset.stderr.strip() or reset.stdout.strip()
            _progress("autoresearch", f"FAIL local reset failed: {err}")
            return SyncResult(ok=False, error=err)
        sha_result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
        if sha_result.returncode != 0:
            return SyncResult(ok=False, error=sha_result.stderr.strip())
        sha = sha_result.stdout.strip()
        _progress("autoresearch", f"OK synced locally sha={sha[:8]}")
        return SyncResult(ok=True, sha=sha)
    except subprocess.TimeoutExpired:
        msg = f"local git timeout after {SSH_TIMEOUT}s"
        _progress("autoresearch", f"FAIL {msg}")
        return SyncResult(ok=False, error=msg)
    except Exception as exc:  # noqa: BLE001
        _progress("autoresearch", f"FAIL {exc}")
        return SyncResult(ok=False, error=str(exc))


def sync_autoresearch_idempotent() -> SyncResult:
    """Pull latest autoresearch on the Windows GPU runner."""
    if use_http_local_preflight():
        return sync_autoresearch_local()
    _progress("autoresearch", f"-> Syncing on GPU runner ({GPU_BOX})...")
    cmd = (
        f"cd {GPU_REPO_PATH} && "
        "git fetch origin && "
        f"git reset --hard origin/{AUTORESEARCH_DEFAULT_BRANCH} && "
        "git rev-parse HEAD"
    )
    try:
        result = subprocess.run(
            ["ssh", *_SSH_OPTS, GPU_BOX, cmd],
            capture_output=True,
            text=True,
            timeout=SSH_TIMEOUT,
        )
        if result.returncode != 0:
            _progress("autoresearch", f"FAIL sync failed: {result.stderr.strip()}")
            return SyncResult(ok=False, error=result.stderr.strip())
        sha = result.stdout.strip().splitlines()[-1]
        _progress("autoresearch", f"OK synced sha={sha[:8]}")
        return SyncResult(ok=True, sha=sha)
    except subprocess.TimeoutExpired:
        msg = f"SSH timeout after {SSH_TIMEOUT}s"
        _progress("autoresearch", f"FAIL {msg}")
        return SyncResult(ok=False, error=msg)
    except Exception as exc:  # noqa: BLE001
        _progress("autoresearch", f"FAIL {exc}")
        return SyncResult(ok=False, error=str(exc))


# -- bootstrap: ensure the repo exists on the GPU runner (first-run only) -------

def bootstrap_autoresearch_local() -> SyncResult:
    """Clone / sync autoresearch locally when GPU runner is this host."""
    repo = LOCAL_REPO_PATH
    _progress("autoresearch", f"-> Checking / bootstrapping locally ({repo})...")
    try:
        if not (repo / ".git").is_dir():
            repo.parent.mkdir(parents=True, exist_ok=True)
            clone = subprocess.run(
                ["git", "clone", AUTORESEARCH_REMOTE, str(repo)],
                capture_output=True, text=True, timeout=SSH_TIMEOUT,
            )
            if clone.returncode != 0:
                err = clone.stderr.strip() or clone.stdout.strip()
                return SyncResult(ok=False, error=f"local clone failed: {err}")
        _progress("autoresearch", "-> Running uv sync --dev locally...")
        try:
            subprocess.run(
                ["uv", "sync", "--dev"],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=SSH_TIMEOUT,
            )
            _progress("autoresearch", "OK uv sync --dev complete")
        except Exception:
            _progress("autoresearch", "WARN uv sync --dev failed (non-fatal: runner may lack uv)")
        return sync_autoresearch_local()
    except subprocess.TimeoutExpired:
        return SyncResult(ok=False, error=f"local bootstrap timeout after {SSH_TIMEOUT}s")
    except Exception as exc:  # noqa: BLE001
        return SyncResult(ok=False, error=f"Bootstrap failed: {exc}")


def bootstrap_autoresearch_on_runner() -> SyncResult:
    """Clone autoresearch on the Windows GPU runner if it does not exist yet."""
    if use_http_local_preflight():
        return bootstrap_autoresearch_local()

    _progress("autoresearch", f"-> Checking / bootstrapping on GPU runner ({GPU_BOX})...")
    check_cmd = f"if not exist {GPU_REPO_PATH} (  git clone {AUTORESEARCH_REMOTE} {GPU_REPO_PATH})"
    try:
        subprocess.run(
            ["ssh", *_SSH_OPTS, GPU_BOX, check_cmd],
            capture_output=True,
            text=True,
            timeout=SSH_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        return SyncResult(ok=False, error=f"Bootstrap failed: {exc}")

    _progress("autoresearch", "-> Running uv sync --dev on GPU runner...")
    uv_cmd = f"cd {GPU_REPO_PATH} && uv sync --dev"
    try:
        subprocess.run(
            ["ssh", *_SSH_OPTS, GPU_BOX, uv_cmd],
            capture_output=True,
            text=True,
            timeout=SSH_TIMEOUT,
        )
        _progress("autoresearch", "OK uv sync --dev complete")
    except Exception:
        _progress("autoresearch", "WARN uv sync --dev failed (non-fatal: runner may lack uv)")

    return sync_autoresearch_idempotent()


# -- GPU lock helpers (read/write swarm_state.md on Mac) -----------------------

def read_swarm_state() -> SwarmState:
    """Parse swarm_state.md into a SwarmState dataclass."""
    if not SWARM_STATE_FILE.exists():
        return SwarmState()

    content = SWARM_STATE_FILE.read_text(encoding="utf-8")
    state = SwarmState()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("- GPU:"):
            state.gpu_status = line.split(":", 1)[1].strip()
        elif line.startswith("val_bpb:"):
            try:
                state.baseline_val_bpb = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("git_sha:"):
            state.baseline_sha = line.split(":", 1)[1].strip()
    return state


def is_gpu_idle() -> bool:
    """Return True if swarm_state.md reports GPU: IDLE."""
    return read_swarm_state().gpu_status.upper() == "IDLE"


def deploy_train_py() -> bool:
    """SCP train.py to the GPU runner."""
    local_train = LOCAL_REPO_PATH / "train.py"
    if not local_train.exists():
        return False
    acquired = _WIN_LM_STUDIO_SLOT.acquire(timeout=SLOT_ACQUIRE_TIMEOUT_SECS)
    if not acquired:
        print(f"[autoresearch] WARN HOP: deploy_train_py timed out waiting for win-lm-studio slot after {SLOT_ACQUIRE_TIMEOUT_SECS}s")
        return False
    try:
        result = subprocess.run(
            ["scp", *_SSH_OPTS, str(local_train), f"{GPU_BOX}:{GPU_REPO_PATH}/train.py"],
            capture_output=True, text=True, timeout=SSH_TIMEOUT,
        )
        return result.returncode == 0
    finally:
        _WIN_LM_STUDIO_SLOT.release()


def run_experiment_on_gpu() -> bool:
    """Dispatch the training run on the GPU runner."""
    acquired = _WIN_LM_STUDIO_SLOT.acquire(timeout=SLOT_ACQUIRE_TIMEOUT_SECS)
    if not acquired:
        print(f"[autoresearch] WARN HOP: run_experiment timed out waiting for win-lm-studio slot after {SLOT_ACQUIRE_TIMEOUT_SECS}s")
        return False
    try:
        cmd = f"cd {GPU_REPO_PATH} && conda run -n autoresearch uv run train.py > run.log 2>&1"
        result = subprocess.run(
            ["ssh", *_SSH_OPTS, GPU_BOX, cmd],
            capture_output=True, text=True, timeout=400,
        )
        return result.returncode == 0
    finally:
        _WIN_LM_STUDIO_SLOT.release()


def fetch_run_log() -> bool:
    """SCP run.log from the GPU runner back to Mac (read-only, no slot needed)."""
    result = subprocess.run(
        ["scp", *_SSH_OPTS, f"{GPU_BOX}:{GPU_REPO_PATH}/run.log", str(LOCAL_REPO_PATH / "log.txt")],
        capture_output=True, text=True, timeout=SSH_TIMEOUT,
    )
    return result.returncode == 0


def init_swarm_state(run_tag: str) -> None:
    """Write a fresh swarm_state.md into the local autoresearch repo."""
    content = textwrap.dedent(f"""\
        # Swarm State - {run_tag}
        <!-- Managed by Perpetua-Tools autoresearch_bridge.py -->
        <!-- DO NOT commit this file; it is ephemeral session state. -->

        ## Current Baseline
        val_bpb: TBD
        git_sha: TBD

        ## Orchestrator Directives
        - Establish baseline: run train.py as-is for the first experiment.

        ## Evaluator Findings
        - (none yet)

        ## Status
        - GPU: IDLE
        <!-- IDLE = safe to dispatch. BUSY = Coder has an active run. -->
        <!-- Only the Coder agent may flip IDLE -> BUSY and back. -->
        <!-- HARDWARE GUARD: Windows loads ONE model at a time: never dispatch while BUSY. -->
    """)
    SWARM_STATE_FILE.write_text(content, encoding="utf-8")


# -- convenience: full pre-run checklist ---------------------------------------

def preflight(
    run_tag: Optional[str] = None,
    *,
    goal: str = "",
    task_type: str = "autoresearch",
    dry_run: bool = False,
    max_cycles: Optional[int] = None,
    use_orama: Optional[bool] = None,
) -> dict:
    """Run the full pre-flight sequence before starting an autoresearch session.

    When ``dry_run`` is True, this returns a side-effect-free plan and skips all
    Claude/plugin/GPU/network substrate actions. Use this before long-running
    goals and before handing state/goals to optional orama methodology.
    """
    if dry_run:
        plan = plan_autoresearch_goal(
            goal or run_tag or "setup autoresearch session",
            task_type=task_type,
            max_cycles=max_cycles,
            use_orama=use_orama,
        )
        return {
            "dry_run": True,
            "plan": plan.to_dict(),
            "plugin_ok": None,
            "plugin_error": None,
            "sync_ok": None,
            "sha": "",
            "error": "",
            "swarm_state_initialised": False,
            "gpu_local": use_http_local_preflight(),
            "preflight_mode": "dry-run",
            "lm_studio_ok": None,
            "lm_studio_error": None,
            "lm_studio_models": "",
        }

    gpu_local = use_http_local_preflight()
    preflight_mode = "http-local" if gpu_local else "ssh"
    plugin = install_autoresearch_plugin()
    sync = bootstrap_autoresearch_on_runner()
    lm = probe_lm_studio_http() if gpu_local else SyncResult(ok=True, sha="skipped")
    initialised = False
    if run_tag and not SWARM_STATE_FILE.exists():
        init_swarm_state(run_tag)
        initialised = True
    return {
        "plugin_ok": plugin.ok,
        "plugin_error": plugin.error,
        "sync_ok": sync.ok,
        "sha": sync.sha,
        "error": sync.error,
        "swarm_state_initialised": initialised,
        "gpu_local": gpu_local,
        "preflight_mode": preflight_mode,
        "lm_studio_ok": lm.ok,
        "lm_studio_error": lm.error,
        "lm_studio_models": lm.sha if lm.ok else "",
    }
