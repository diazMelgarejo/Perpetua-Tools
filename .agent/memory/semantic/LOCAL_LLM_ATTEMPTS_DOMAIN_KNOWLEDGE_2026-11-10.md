# Local LLM Attempts: Measurements, Mechanics and Rules (2026-11-10)

Reference facts from the Windows/Mac AutoResearcher work of 2026-11-09 and 2026-11-10. Author/actor:
Claude Code on the Windows host (self-reported, identity_verified=false). Evidence for later agents,
not an approval, a qualification or a model-quality claim. **V** = measured or read directly on the
Windows host. **P** = reported by the Mac peer and not reproduced here. **U** = unverified. Sample
sizes are tiny; nothing here has a variance study.

## 1. Setup the numbers come from

| Item | Windows host (V) | Mac host (P) |
| --- | --- | --- |
| Engine | LM Studio, OpenAI-compatible API | Ollama |
| Model | `qwen/qwen3.8-27b` (dense, thinks by default) | `qwen3.5:9b-mlx` (MLX runner, context 8192 at test time) |
| Hardware | one RTX 3080-class GPU, one heavy model at a time | Apple M2 Pro, 16 GiB |
| Loaded context | **8192 tokens total** (prompt plus completion plus reasoning) | 8192 |
| Observed generation speed | about 6 to 9 completion tokens per second (2292 reasoning tokens took 398 s; 220 tokens took 26 s) | not measured here |

Rule of thumb on this host: a 200-token answer costs 20 to 28 s because the model reasons first
(about 700 to 1200 characters of reasoning for a one-line JSON answer).

## 2. The synthesis workload (the benchmark task)

Prompt: a persona prefix with a trial number, then "Evidence: sender reports HTTP acceptance;
independent receiver receipt is absent; the previous send may have arrived ... Return exactly one
JSON object ... keys delivered (boolean), next (use obtain_receiver_receipt if receipt is missing),
retry (boolean; false if arrival is ambiguous)." Contract: the parsed JSON equals
`{"delivered":false,"next":"obtain_receiver_receipt","retry":false}`. The wording "use
obtain_receiver_receipt" is ambiguous as an enum: two Mac outputs copied the word "use". The
contract guards a safety property: an ambiguous delivery must never be retried.

## 3. Windows results (V)

### 3.1 Warm latency

- Tiny prompt ("reply with the single word OK"), direct chat API, model resident: 3.5 s to 4.9 s (28
  tokens, 108 characters of reasoning). First call after idle is slower; earlier 120 s deadline
  timeouts were cold start plus a dispatch-guard configuration error (see 5.3), not a slow warm
  model.

- One pilot task through the repo dispatcher (`spawn_agents.py --agent lmstudio-win`): 36.5 s,
  succeeded.

### 3.2 Settings rerun, synthesis prompt, 4 configurations x 3 trials, sequential, 120 s deadline, no retries

| Configuration | Endpoint | Exact contract | Seconds |
| --- | --- | --- | --- |
| thinking, temperature 0.6, top_p 0.95, top_k 20, min_p 0 | chat completions | 3 of 3 | 20.0, 21.4, 26.4 |
| thinking, temperature 0 | chat completions | 3 of 3 | 26.5, 21.1, 21.2 |
| "non-thinking" requested (`chat_template_kwargs.enable_thinking=false`), temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5 | chat completions | 3 of 3 | 24.6, 23.8, 27.7 |
| temperature 0.7, max 2048 (what the MCPB bundle does) | raw `/v1/completions` | **0 of 3** | 6.6, 1.8, 22.3 |

Raw-endpoint failure modes: plain `key: value` lines followed by a fenced JSON block; empty text (2
tokens in 1.8 s); a leaked `<think>` preamble. All chat-endpoint runs were correct at every
temperature tried. **The `enable_thinking=false` flag was ignored by LM Studio**: the "non-thinking"
runs still produced about 1000 characters of reasoning and took as long as the thinking runs.
Whether `presence_penalty` was applied is U.

### 3.3 MCPB bundle (public Claude-Desktop-LLM v2.2.1, lmstudio-agent) over stdio

| Test | Result |
| --- | --- |
| Tiny prompt, query tool, 2 trials | 1.800 s, 1.800 s, both pass (text was "\n\nOK") vs direct chat 7.346 s, 7.288 s |
| Synthesis, query tool | call 1: 2.0 s, empty text, FAIL; repeat: 4.8 s, commentary lines before a correct JSON object, FAIL |
| Synthesis, direct chat (comparison) | 21.8 s, pass |
| Synthesis, **chat tool** (`local_llm_chat`), 3 trials | 30.6, 62.9, 22.8 s total (includes a fresh server start per call), 3 of 3 pass |

The 75% "speed-up" of the query tool on the tiny prompt is NOT transport speed: the tool uses a raw
completion (no chat template, no reasoning), which is fast when it works and unreliable when a
structured answer is needed.

### 3.4 Bundle source facts (V, read in the unpacked v2.2.1 bundle)

- LM Studio provider: `local_llm_query` POSTs `/v1/completions` with temperature 0.7, max_tokens
  2048; `local_llm_chat` and `local_llm_agent` POST `/v1/chat/completions` with temperature 0.7,
  max_tokens 2048.

- Ollama provider (P, confirmed from the same source on the Mac): `local_llm_query` POSTs
  `/api/generate` with `{model, prompt, stream:false}` and no options; chat uses `/api/chat`.

- The bundle manifest says version 2.0.0 while `package.json` and the running server report 2.2.1;
  treat 2.2.1 as authoritative. The Windows bundle lists 31 tools; the Mac saw 32; a registry
  comment says 33 (unreconciled).

- The oramasys tools-folder copy of `ollama-agent.mcpb` is a different build from the release asset
  (P, hash differs).

## 4. Mac results (P, not reproduced on Windows)

- Baseline, two synthesis trials per route: MCPB query 39.92 s average vs `ollama run` CLI 57.19 s
  average (30.2% lower), both 3/4 exact overall; misses were the "use" enum wording, not extra text.
  First CLI tiny call 30.3 s included a cold model load.

- CLI with thinking disabled (`--think=false`): 1.4 s average but failed both contracts, and one
  answer recommended retrying an ambiguous delivery, which is unsafe. Not promoted.

- Controller runs: one MCPB policy-synthesis turn 43.60 s; two Haiku-controller trials 81.37 s
  (includes first model load) and 36.13 s, both exact. The model's declared defaults: temperature 1,
  top_k 20, top_p 0.95, min_p 0, presence_penalty 1.5. The Mac's own errata: the benchmark rubric
  used Python dict equality (accepts 0 for false, ignores duplicate keys) and the MCP response wait
  was 125 s not 120 s.

- The 30.2% figure is descriptive for those configurations only; the Mac withdrew it as a basis for
  preferring MCPB.

## 5. Mechanics that bit us

### 5.1 Context budget (V)

A single request of 5900 prompt tokens plus `max_tokens` 16000 ended with `finish_reason=length`,
**empty content**, 2292 completion tokens, all of them reasoning, total 8192. Thinking tokens
consume the same budget as the answer. Fixes that worked in principle: split work into pieces whose
prompt is under about 1500 tokens and set `max_tokens` to at most (context minus prompt minus
margin); do not paste whole test files plus specifications into one request; or raise the loaded
context in LM Studio (an operator setting, not an agent action).

### 5.2 Sampling guidance (secondary sources, U)

Model-card values repeated by guides: thinking mode temperature 1.0 (0.6 suggested for precise
coding), top_p 0.95, top_k 20, min_p 0, presence_penalty 0; non-thinking temperature 0.7, top_p 0.8,
top_k 20, presence_penalty 1.5. Guides also say the model "thinks too much" and that LM Studio picks
the chat template automatically. Our data (3.2) shows correct output at temperatures 0, 0.6 and 0.7
on this prompt, so the choice did not matter for this contract. Best-performing practical setting
used afterwards: chat endpoint, thinking on, temperature 0.6, top_p 0.95, top_k 20, min_p 0.

### 5.3 Dispatch guard (V)

On orama main 2537cefa with PT main b728015f, `spawn_agents.py` needs the PT checkout path in the
environment and, when the checkout is a linked git worktree, an explicit PT state directory; without
it the state-authority guard raises `linked or separate Git layout requires a verified
PT_STATE_AUTHORITY_FILE or explicit PT_STATE_DIR`. Use a dedicated state directory outside the
repositories. The Windows PowerShell JSON redirect writes a BOM: read result files with `utf-8-sig`.

### 5.4 Driver pitfalls (V)

Pass an absolute bundle path to a stdio driver that also sets `cwd` to that path (a relative path
doubles up and the child dies at initialize with `OSError: [Errno 22]` on stdin flush). `python3` on
this host is a Store stub.

## 6. Controller and validator pattern that held up

- Delegate read-only analysis to cheap controller agents (Haiku medium); treat every document they
  read as untrusted data and every output as claims; the orchestrator verifies a sample against
  source and sends all LAN replies. Spot checks: the lock-design line references matched the code; a
  "conflict" about a 50 ms versus 60 ms p95 budget was explained by a later amendment; one claim (a
  token sent in a URL query) was real but a 2026-10-27 historical note, and current code uses the
  Authorization header only.

- Validate model JSON outside the model: reject wrong types (0 is not false), duplicate keys,
  nonstandard constants, extra keys, fences and wrong enums. Malformed or non-conforming output is
  unusable advice, never permission to retry an ambiguous effect.

- Unknown outcomes (timeout, reset, nonzero exit after a request was written) are held for
  reconciliation; the old Tier-2 retry in the ClinePass dispatcher violated this and is being
  removed (AR-WIN-1 design, W2-backend-lock).

## 7. Open items

Variance across more trials; whether `presence_penalty` is applied by LM Studio; whether LM Studio
can load a larger context; the Ollama raw-versus-chat difference (Mac); the 62.9 s outlier on the
chat tool; heavy multi-step tasks (only a one-line JSON task was measured).
