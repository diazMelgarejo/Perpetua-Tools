# Validated agent handoff — v1

Use [the JSON example](examples/handoff-packet-v1.json) as the machine source
of truth. This document is the human companion; free-form Markdown alone is
never enough to admit work through the validated queue path.

## Required workflow

1. Create a JSON packet from the example.
2. Record the exact starting head, current/commit head, changed files, root
   cause, commands actually run, their observed results, and known follow-up.
3. Keep `merge_authorized` and `deployment_authorized` false. A packet cannot
   grant those powers.
4. Validate before dispatch:

   ```bash
   python scripts/agent_coordination.py handoff validate handoff.json
   ```

5. Admit only validated packets:

   ```bash
   python scripts/agent_coordination.py queue add handoff-validation Phase-1 \
     --handoff handoff.json --priority high
   ```

6. The receiving worker acknowledges, claims its task, and sends its own
   explicit heartbeat pulse periodically while it is active:

   ```bash
   python scripts/agent_coordination.py heartbeat pulse <agent-id>
   ```

## Liveness rule

`log()` communicates status; it does **not** refresh liveness. Queue admission
also does not pulse the assigned worker, because a coordinator cannot prove
that another process is alive. A long-running worker is ACTIVE only when it
continues to send explicit heartbeat pulses. If pulses stop, the normal
IDLE/STALLED/DEAD transitions remain in force even if board logs continue.

## Handoff checklist

| Check | Required proof |
| --- | --- |
| Human scope | `human_authorized: true`; no merge/deploy authority in packet |
| Source line | branch plus valid `starting_head` |
| Completion head | `current_head == commit_sha` |
| Evidence | non-empty changed files, root cause, and test commands/results |
| Locality | reviewed work stays on the target feature branch |
| Handoff | receiver acknowledges, claims, and emits a real pulse |

## Failure semantics

Validation errors, conflicting CLI source fields, malformed JSON, unsupported
authority, missing evidence, and inconsistent heads reject admission before a
queue task or admission audit is written. Repair the packet, validate again,
then enqueue. Do not bypass validation by replacing it with a board log or an
unstructured file drop.
