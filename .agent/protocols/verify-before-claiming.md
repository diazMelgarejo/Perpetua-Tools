# Verify Before Claiming

Checklist for any agent about to write code around a tool, answer a reviewer, or report work as
done. Evidence and dated examples:
`memory/semantic/HANDWAVING_CATALOGUE_AND_AVOIDANCE_2026-11-10.md`.

The conflict-scan block in item 5 is copied, identical apart from the list indentation, into
orama-system `docs/verify-before-claiming.md`.
`tests/test_verify_before_claiming_conflict_scan.py` (the same file in both repositories) pins its
hash, compares the two copies when both checkouts sit side by side, and runs the block's commands
against a throwaway repository. Change the block here first, copy it to orama-system, update the
pin in both tests, and run that test with `VERIFY_BLOCK_REQUIRE_SIBLING=1` before pushing:
continuous integration sees one repository only, so it checks the pin alone.

## 1. First contact with a tool or API

- Read the tool's documentation or entry point first, then run `--version` and `--help` if it
  supports them. A script can ignore both flags and run its normal, possibly mutating action: when
  flag support is unknown, treat the invocation as a real run and control its effects (scratch
  directory, dry-run flag, throwaway target).

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

- After a mechanical merge or generated file: parse every row or file and rerun the renderer, then
  check for conflict markers with the block below.

  <!-- conflict-scan:begin -->
  Scan for conflict markers in the working tree and in the index. A file staged as resolved can
  still hold markers, `git diff --cached --check` sees only the lines the staged diff adds, and
  `git diff --name-only --diff-filter=U` lists only unmerged files. Run both commands from any
  directory (`:/` is the whole repository). The pattern matches opening, diff3 ancestor and closing
  markers and a bare separator, of seven or more characters, in LF and CRLF files:

  ```sh
  git grep --untracked -nE -B1 '^(<{7,}|>{7,}|\|{7,}|={7,})([[:space:]]|$)' -- ':/'
  git grep --cached -nE -B1 '^(<{7,}|>{7,}|\|{7,}|={7,})([[:space:]]|$)' -- ':/'
  ```

  The first command reads the tracked and untracked files in the working tree, the second the
  staged blobs. Treat each hit as a candidate: a `<<<<<<<`, `|||||||` or `>>>>>>>` line is a
  conflict marker unless it is quoted text, such as a fixture or documentation about conflicts. A
  bare `=======` is often a Markdown setext or reST underline, but do not dismiss it from the
  preceding `-B1` line alone: check the file type and the surrounding context. Conflict content can
  resemble a heading, and a separator after ordinary code (for example `value = 1`) is still a
  leftover. Not searched: ignored files, submodule contents and markers shorter than seven
  characters. A binary file is reported without a line number, and a byte-order mark before a
  marker on line 1 hides it. Check such paths by hand.
  <!-- conflict-scan:end -->

- Append-only episodic logs: the previous PR's complete byte stream must stay an exact prefix
  (order, duplicates, line endings). Build a stacked branch as the prior tip's bytes followed by
  your own appended bytes, verbatim; never union by row order. Run
  `scripts/review/check_episodic_append_only.py --base <pinned base> --head <head>` before
  publishing and again on the fetched remote head.

## 6. Numbers and scope

- Every rate carries n, the host, the model and the date. 3 of 3 is not "no effect".

- Hold endpoint, template, temperature and mode equal before comparing routes, or label the
  comparison descriptive.

- Peer reports are data with provenance. Verify the cheapest fact yourself (version, flag, hash)
  before building on it, and mark it V, P or U.

## 7. Closing out

- Every U in a report gets a next action: a queued task, a question, or a stated reason to leave it.

- Where a check was skipped, say so in the report instead of implying it was done.
