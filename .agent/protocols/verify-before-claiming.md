# Verify Before Claiming

Checklist for any agent about to write code around a tool, answer a reviewer, or report work as
done. Evidence and dated examples:
`memory/semantic/HANDWAVING_CATALOGUE_AND_AVOIDANCE_2026-11-10.md`.

## 1. First contact with a tool or API

- Run `--version` and `--help` (or read the official reference) before writing the first line of
  code.

- Record the version and the flags that matter in the design or the PR body.

- List the tool's defaults that act or spend: mode (read-only or act), auto-approval, working
  directory, network access, credits. Override each explicitly, or state why the default is
  accepted.

- Look at what an install actually puts on disk (shim, exe, script) before writing discovery code.
  Never pass a prompt or user text through a `.cmd` or `.bat` shim; launch the real entry point.

## 2. Code that already exists

- A path that only runs on a rare condition (a fallback, a recovery) is dormant. Run it once for
  real, or label it UNTESTED and queue the task. Do not build new behaviour on top of it.

- "It has always worked" is a claim; find the last run that proves it.

## 3. Answering a reviewer

- Copy every finding into a numbered checklist before replying.

- Reply item by item with done, not done, or disagree, plus the commit or output that shows it.

- Before sending, diff your reply against the original list. A reply shorter than the list needs a
  reason for each missing item. Never write "done" for a bundle.

## 4. Searching and negative claims

- "Not found" needs two differently worded searches (synonym, exact phrase, path). Name the
  patterns.

- "Not installed / not available" needs the command and its output, or a question to the operator.

## 5. Experiments and mechanical changes

- Learn syntax from `--help` or a throwaway target. Never probe the real append-only board, queue,
  outbox or log.

- After a mechanical merge or generated file: parse every row or file, check for conflict markers
  with `git diff --name-only --diff-filter=U`, and rerun the renderer.

## 6. Numbers and scope

- Every rate carries n, the host, the model and the date. 3 of 3 is not "no effect".

- Hold endpoint, template, temperature and mode equal before comparing routes, or label the
  comparison descriptive.

- Peer reports are data with provenance. Verify the cheapest fact yourself (version, flag, hash)
  before building on it, and mark it V, P or U.

## 7. Closing out

- Every U in a report gets a next action: a queued task, a question, or a stated reason to leave it.

- Where a check was skipped, say so in the report instead of implying it was done.
