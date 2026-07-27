"""
Hermes plugin: orama-pipeline
Registers the Orama 5-stage pipeline as a native Hermes toolset.
Drop into ~/.hermes/plugins/ or .hermes/plugins/ — auto-discovered on startup.
"""
from hermes.plugins import Plugin, tool
from hermes_harness import run_orama_pipeline, spawn_hermes_agent

class OramaPipelinePlugin(Plugin):
    name = "orama-pipeline"
    description = "Orama 5-stage multi-agent pipeline tools"

    @tool
    def orama_run(self, task: str) -> str:
        """Run the full Orama pipeline for a complex task."""
        results = run_orama_pipeline(task)
        return "\n\n".join(f"[{r['stage']}] {r['result']}" for r in results)

    @tool
    def orama_stage(self, stage: str, task: str) -> str:
        """Run a single Orama stage (context/architect/refiner/executor/verifier/crystallizer)."""
        result = spawn_hermes_agent(stage, task)
        return result["result"]

plugin = OramaPipelinePlugin()
