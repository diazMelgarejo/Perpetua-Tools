# Pending actions: Windows RTX 5080 agents (opened 2026-11-28)

**For:** the agents on the Windows RTX 5080 node (`win-rtx5080`).
**Status:** open, not started. This is a follow-up list, not an approval to load or benchmark.

## Rules that apply first

- At most one local model loaded on the node at a time, across all engines.
- Load nothing without the operator's explicit go for that load.
- Do not make this model a default or give it a route until it has run on the node.

## Follow up

1. **The file:**
   [FreedomAISVR/DiffusionGemma-26B-A4B-it-NVFP4-GGUF](https://huggingface.co/FreedomAISVR/DiffusionGemma-26B-A4B-it-NVFP4-GGUF),
   `diffusiongemma-26b-a4b-it-nvfp4.gguf`. Check whether it loads in any runtime, including the
   draft build below. Its card lists the architecture as `gemma4`; confirm that against the runtime.
2. **llama.cpp support:**
   [ggml-org/llama.cpp#24423](https://github.com/ggml-org/llama.cpp/pull/24423) was a draft on
   2026-11-28 and runs the model through `llama-diffusion-cli`. Watch for the merge.
3. **LM Studio support:**
   [lmstudio-ai/lms#583](https://github.com/lmstudio-ai/lms/issues/583) was open on 2026-11-28.

## What was checked on 2026-11-28, from the Mac, without loading anything

- [Google's model card](https://huggingface.co/google/diffusiongemma-26B-A4B-it) describes a
  text-diffusion model: text, image and video in, text out.
- The quantiser's card calls it text-to-image. `config/models.yml` and `hardware/SKILL.md` repeat
  that wording (`image-generation` role, `lm-studio` backend). The two cards disagree; the entry is
  unchanged until the operator decides.
- Model file 14.4 GB plus a 1.19 GB vision file, on a 16 GB card. The quantiser recommends 24 GB or
  more for full GPU offload.

## Report back

For each item: what you ran or read, the date, the exact versions, and the result. Send it to the Mac
peer inbox and say plainly what was not run.
