# Offline / sandbox agent report

This Markdown format is the **canonical** status report for agents that
cannot reach the LAN GossipBus, the coordination queue, or the operator
host — including Cursor Cloud / isolated sandboxes and any agent that is
**not on the same machine**.

When the queue is reachable, prefer the validated JSON handoff
([`agent-handoff-template.md`](agent-handoff-template.md)) and admit it
with `python scripts/agent_coordination.py handoff validate` before
`queue add`. This document does **not** replace that path.

The shared Grok Bot skill for this workflow is named
`offline-sandbox-agent-report`. Do not follow a sand-workflow URL; use
that skill name, this document, or
`.agents/skills/offline-sandbox-agent-report/SKILL.md`.

## When to use

- No LAN / inter-host GossipBus
- Isolated sandbox or Cursor Cloud VM
- Different machine from the operator host
- `scripts/agent_coordination.py` (handoff validate / queue / heartbeat)
  is unreachable

Do not use this report to bypass validation once the queue is back.
Convert the filled sections into a JSON packet and admit it then.

## Required sections

Copy the template below. Fill every field. Use `unknown` or `n/a` only
when the fact cannot be observed from this sandbox — never invent SHAs,
test results, or authority.

```markdown
# Offline / sandbox agent report

## Identity
- reporter: <agent or bot name>
- role: <role>
- session_id: <id or n/a>
- job_id: <id or n/a>
- task_id: <short slug>
- assigned_agent_id: <id or n/a>
- intent: <one sentence>

## Locality
- repo: Perpetua-Tools
- branch: <exact branch>
- worktree: <path or n/a>
- starting_head: <full or abbreviated SHA observed at start>
- current_head: <SHA of this work>
- commit_sha: <must equal current_head when work is committed>
- files_changed:
  - <path>
  - <path>

## Outcome
- status: done | blocked | needs-operator
- root_cause_addressed: <one paragraph>
- known_risks_or_follow_up: <text or none>

## Evidence
- tests:
  - command: <exact command>
    result: <observed stdout/summary, not a claim>
  - command: <exact command>
    result: <observed result>
- other proof: <diffstat, log paths, or n/a>

## Authority (never grant from this file)
- human_authorized: true | false
- merge_authorized: false
- deployment_authorized: false

## Reachability
- queue_reachable: false
- lan_reachable: false
- same_machine_as_operator: false
- heartbeat_pulsed: false  # cannot prove liveness for another host
```

## Field mapping to the JSON packet

Use the same names as
[`examples/handoff-packet-v1.json`](examples/handoff-packet-v1.json)
so a later operator can paste this report into a validated packet
without renaming.

| Markdown field | JSON key |
| --- | --- |
| `session_id` | `session_id` |
| `job_id` | `job_id` |
| `task_id` | `task_id` |
| `assigned_agent_id` | `assigned_agent_id` |
| `role` | `role` |
| `intent` | `intent` |
| `branch` | `branch` |
| `worktree` | `worktree` |
| `starting_head` | `starting_head` |
| `current_head` | `current_head` |
| `commit_sha` | `commit_sha` |
| `files_changed` | `files_changed` |
| `root_cause_addressed` | `root_cause_addressed` |
| tests command/result | `tests[].command` / `tests[].result` |
| `known_risks_or_follow_up` | `known_risks_or_follow_up` |
| `human_authorized` | `human_authorized` |
| `merge_authorized` | `merge_authorized` (stay `false`) |
| `deployment_authorized` | `deployment_authorized` (stay `false`) |

`current_head` must equal `commit_sha` when the work is committed.
Do not leave those two disagreeing.

## Rules

1. Free-form Markdown is never enough to admit work through the
   validated queue. This report is a **fallback packet for humans and
   later conversion**, not an admission contract.
2. Keep `merge_authorized` and `deployment_authorized` false. A
   sandbox report cannot grant merge or deploy.
3. Record commands actually run and their observed results. Do not
   write “tests passed” without the command line and the observed
   summary.
4. Do not pulse heartbeat for an agent you do not control and cannot
   reach. Offline reporters stay `heartbeat_pulsed: false`.
5. Do not paste secrets, tokens, raw prompts, or live LAN IPs.
6. Do not treat a board `log()` or this Markdown file as liveness.
7. When the queue becomes reachable, validate JSON before `queue add`.
   Do not enqueue this Markdown file as if it were the packet.

## Optional monitorability

If the later JSON packet includes `monitorability`, follow
[`agent-handoff-template.md`](agent-handoff-template.md): redacted
refs only, no raw reasoning, and `block` is invalid in v1. Omit the
envelope from this Markdown report unless the operator asked for it
and every value is already a redacted id.
