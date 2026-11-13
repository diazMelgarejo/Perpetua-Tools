# W&B inference working configuration

Evidence: 2026-11-13 live chat completions. GossipBus note
`485cda77bc0e4dcebe949d52e850af7f`, topic
`WANDB_INFERENCE_WORKING_CONFIG_20261113`. No secret values belong in
this card.

This route is the OpenAI client plus Weave. It is not the Cline CLI.

## Use this

Shell-source the operator W&B env file before any Python process reads
it. That file contains a shell metacharacter. A raw text parse is a
different value and returns 401. The shell-sourced value is the one
that authenticates.

```python
import os
import openai
import weave

weave.init(os.environ["DEEPSEEK_V4_FLASH_WANDB_PROJECT"])
client = openai.OpenAI(
    base_url="https://api.inference.wandb.ai/v1",
    api_key=os.environ["DEEPSEEK_V4_FLASH_WANDB"],
    project=os.environ["DEEPSEEK_V4_FLASH_WANDB_PROJECT"],
)
response = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-V4.1-Flash-1017",
    messages=[{"role": "user", "content": "Reply with exactly PING"}],
    max_tokens=16,
)
```

Do not print `DEEPSEEK_V4_FLASH_WANDB`. Do not put it in argv, a prompt, a commit, or a gossip payload.

## What returned text

| Model | project omitted | project = DEEPSEEK_V4_FLASH_WANDB_PROJECT | CoreWeave team/project string |
| --- | --- | --- | --- |
| deepseek-ai/DeepSeek-V4.1-Flash-1017 | text | text | 401 |
| deepseek-ai/DeepSeek-V4.1-Flash | text | text | 401 |
| deepseek-ai/DeepSeek-V4-Flash-0731 | text | text | 401 |
| deepseek-ai/DeepSeek-V4-Flash | 404 | 404 | 401 |

`weave.init` on `DEEPSEEK_V4_FLASH_WANDB_PROJECT`, then a chat with no
extra project argument, returned text and logged the call.

## Do not use

- A CoreWeave team/project string. Chat returns 401. `weave.init` on
  that string is permission denied for this key.
- Model id `deepseek-ai/DeepSeek-V4-Flash`. This endpoint returns 404.
- The Cline CLI (`-P openai-compatible` with
  `deepseek-ai/DeepSeek-V4.1-Flash-1017`) after the provider entry passes
  the 3.0.74 `tokenSource` / `updatedAt` check in lesson_8e02c7fd391d.
  If that check passes and Cline still returns `invalid model ID` for the
  same key and model the OpenAI client completes, use the OpenAI client.
- A raw parse of the env file. Only the shell-sourced value authenticates.

## Stick to this

Shell-source the env file. OpenAI client at
`https://api.inference.wandb.ai/v1`. Key variable
`DEEPSEEK_V4_FLASH_WANDB`. Project variable
`DEEPSEEK_V4_FLASH_WANDB_PROJECT`. Model
`deepseek-ai/DeepSeek-V4.1-Flash-1017`. Weave init on that same project
variable.

The same card is canonical in orama-system at
`bin/orama-system/skills/cline-openclaw-agent/references/wandb-inference-working-config.md`.
