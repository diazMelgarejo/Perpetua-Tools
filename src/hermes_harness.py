"""
hermes_harness.py — Orama/Perpetua orchestrator for Hermes agents.

Spawns Hermes AIAgent instances for each Orama 5-stage pipeline step.
All API keys resolved from .env / .env.local (repo root then $HOME).
Never prompts for credentials.
"""
from __future__ import annotations
import os
import concurrent.futures
from pathlib import Path
from dotenv import load_dotenv

# Load .env hierarchy: repo root → $HOME (never prompt)
for env_path in [Path(".env.local"), Path(".env"),
                 Path.home() / ".env.local", Path.home() / ".env"]:
    if env_path.exists():
        load_dotenv(env_path, override=False)

from run_agent import AIAgent  # noqa: E402 — after env load

# ── Model tier policy (matches Orama frugality chain) ──────────────────────
STAGE_MODELS: dict[str, str] = {
    "context":      os.getenv("HERMES_CONTEXT_MODEL",     "google/gemini-3-flash-preview"),
    "architect":    os.getenv("HERMES_ARCHITECT_MODEL",   "anthropic/claude-sonnet-4"),
    "refiner":      os.getenv("HERMES_REFINER_MODEL",     "anthropic/claude-sonnet-4"),
    "executor":     os.getenv("HERMES_EXECUTOR_MODEL",    "anthropic/claude-sonnet-4"),
    "verifier":     os.getenv("HERMES_VERIFIER_MODEL",    "anthropic/claude-sonnet-4"),
    "crystallizer": os.getenv("HERMES_CRYSTAL_MODEL",     "anthropic/claude-opus-4"),
}

# ── Soul registry (matches orama-system SOUL.md pattern) ───────────────────
STAGE_SOULS: dict[str, str] = {
    "context":     "You are Cass, the Meticulous Cartographer. Map scope, sources, and assumptions. Output: structured context manifest.",
    "architect":   "You are Aria, the Boundary-Minded Designer. Produce interfaces, risks, and acceptance tests.",
    "refiner":     "You are Sena, the Constructive Editor. Run up to 3 elegance loops. Threshold: 0.8.",
    "executor":    "You are Rourke, the Literal Builder. Produce safe patches. Never commit, push, or silently expand scope.",
    "verifier":    "You are Vera, the Professional Skeptic. Attempt to disprove every claim. Block until PASS.",
    "crystallizer":"You are Crystal, the Careful Archivist. Synthesize approved lessons into MEMORY.md and LESSONS.md.",
}


def spawn_hermes_agent(stage: str, task_prompt: str, **kwargs) -> dict:
    """Spawn a single Hermes AIAgent for one Orama pipeline stage."""
    agent = AIAgent(
        model=STAGE_MODELS[stage],
        quiet_mode=True,
        skip_context_files=False,   # load AGENTS.md / SOUL.md from working dir
        skip_memory=(stage in {"context", "architect"}),  # lean on hot stages
        ephemeral_system_prompt=STAGE_SOULS[stage],
        max_iterations=kwargs.get("max_iterations", 50),
        platform=kwargs.get("platform", None),
    )
    result = agent.chat(task_prompt)
    return {"stage": stage, "model": STAGE_MODELS[stage], "result": result}


def run_orama_pipeline(task: str, parallel_stage4: bool = True) -> list[dict]:
    """
    Execute the full Orama 5-stage pipeline via Hermes agents.
    Stages 1-3 are sequential. Stage 4 (executor + verifier) is parallel.
    Stage 5 crystallizes the approved outputs.
    """
    results: list[dict] = []

    # Stages 1–3: sequential context → architect → refiner
    for stage in ("context", "architect", "refiner"):
        r = spawn_hermes_agent(stage, task)
        results.append(r)
        task = f"Previous stage output:\n{r['result']}\n\nTask: {task}"  # chain context

    # Stage 4: parallel executor + verifier
    if parallel_stage4:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            futs = {ex.submit(spawn_hermes_agent, s, task): s
                    for s in ("executor", "verifier")}
            for fut in concurrent.futures.as_completed(futs):
                results.append(fut.result())
    else:
        results.append(spawn_hermes_agent("executor", task))
        results.append(spawn_hermes_agent("verifier", task))

    # Stage 5: crystallizer receives all prior results
    summary = "\n\n".join(f"[{r['stage']}]\n{r['result']}" for r in results)
    results.append(spawn_hermes_agent("crystallizer", summary))

    return results


if __name__ == "__main__":
    import sys, json
    task_input = " ".join(sys.argv[1:]) or "Explain the Orama 5-stage pipeline."
    output = run_orama_pipeline(task_input)
    print(json.dumps(output, indent=2))
