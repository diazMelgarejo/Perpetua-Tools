# Re-anchor triage mechanics (read-only): procedure, decision table and script

**Author:** claude-sonnet-5-5, written 2026-10-23 UTC. Reference companion to the session
chronicle of the same date; nothing existing is edited.
**Status:** reference. Steps 1 to 6 and 10 change nothing in any repository (they write scratch
files outside it). Steps 7 to 9 are mutating: step 7 adds tag refs; step 8 adds a worktree and a
branch ref and edits that branch's config; step 9 writes one commit, which updates the new
branch ref, its index and its worktree.

## 1. When to use this

Use it when `main` was rewritten (expunge, scrub, squash-rebundle) and a stale checkout or branch
still carries commits that `git cherry` reports as unique. The question is not how far behind the
checkout is. Ahead/behind counts and merge-base are invalid across a rewrite. The question is
whether any content is actually missing from `main`. Related lessons: `00f3e059181b`,
`1888719f8a52`, `19b69065cb5e`, `1103c662e580`.

## 2. Preconditions

* git 2.38 or newer for `git merge-tree --write-tree` (verified with 2.54).
* Python 3 on PATH; the script uses only the standard library.
* An already-fetched reference to the rewritten history (`origin/main`). The stock scan script
  runs `git fetch --prune origin`, which updates and prunes remote-tracking refs. For a strict
  read-only audit use the no-fetch copy in step 2.
* Anchors used below: `$REPO` (the repository root) and `$SCRATCH` (a temporary folder outside
  any repository). Never write real local paths into tracked files.

## 3. Procedure

1. Snapshot every ref so the end of the run can prove nothing moved.

    ```bash
    git -C "$REPO" for-each-ref --format='%(refname) %(objectname)' > "$SCRATCH/refs-before.txt"
    ```

2. Tree-twin scan without the fetch. Verdicts are MERGED/in-main, NEEDS-REANCHOR (graft N commits
   onto the deepest twin), ORPHAN and NO-TWIN.

    ```bash
    sed -E 's/git fetch --prune origin/true/' "$REPO/scripts/git/reanchor_scan.sh" \
      > "$SCRATCH/reanchor_scan_nofetch.sh"
    bash "$SCRATCH/reanchor_scan_nofetch.sh" "$REPO" origin/main all
    ```

3. Collect the patch-unique commits of the tip under review (full SHAs, one per line).

    ```bash
    git -C "$REPO" cherry origin/main HEAD | grep '^+' | awk '{print $2}' > "$SCRATCH/unique.txt"
    ```

4. See how widely those commits are shared. Many branches carrying the same set means a shared
   old tail, not many distinct contributions.

    ```bash
    for c in $(cat "$SCRATCH/unique.txt"); do
      git -C "$REPO" branch -a --contains "$c" --format='%(refname:short)'
    done | sort | uniq -c | sort -rn | head -40
    ```

5. Extract the script from section 6, then triage. The extraction command writes the only fenced
   Python block of this document to the path the commands below use. Run all three modes.

    ```bash
    DOC=.agent/memory/semantic/REANCHOR_TRIAGE_MECHANICS_2026-10-23.md   # path inside the repo
    awk '/^```python$/{f=1;next} /^```$/{if(f)exit} f' "$DOC" > "$SCRATCH/reanchor_triage.py"
    cd "$SCRATCH"
    python -I reanchor_triage.py "$REPO" classify --list "$SCRATCH/unique.txt"
    python -I reanchor_triage.py "$REPO" contain  --list "$SCRATCH/unique.txt"
    python -I reanchor_triage.py "$REPO" residual --list "$SCRATCH/unique.txt"
    ```

6. Prove that a removal in `main` was deliberate before treating its absence as a gap.

    ```bash
    git -C "$REPO" log origin/main -S'<symbol>' --format='%h %ad %s' --date=short -- <path>
    git -C "$REPO" grep -n -E '<symbol>' origin/main
    ```

7. Safety tags (mutating, local only). Restore with `git branch <name> <tag>`.

    ```bash
    git -C "$REPO" tag "backup/pre-reanchor-<timestamp>-<label>" <ref>
    ```

8. Disposable worktree and branch (mutating, local only). Remove the upstream immediately so a
   bare push cannot target `main`.

    ```bash
    git -C "$REPO" worktree add -b <yyyy-mm-dd-NNN-brief-summary> "$WORKTREE" origin/main
    git -C "$REPO" branch --unset-upstream <yyyy-mm-dd-NNN-brief-summary>
    ```

9. Commit with every hook active (mutating, local only: one commit; the new branch ref, its index
   and its worktree change). Put the pinned markdown linter on PATH first; the message ends with
   the attribution line required by the organization's policy.

    ```bash
    git -C "$WORKTREE" commit -F "$SCRATCH/commit-msg.txt"
    ```

10. Re-prove the end state: the ref diff against the snapshot shows only the intended additions,
    the original checkout is unchanged, and a read-only merge rehearsal exits 0.

    ```bash
    git -C "$REPO" for-each-ref --format='%(refname) %(objectname)' > "$SCRATCH/refs-after.txt"
    diff "$SCRATCH/refs-before.txt" "$SCRATCH/refs-after.txt"
    git -C "$REPO" merge-tree --write-tree origin/main <branch>; echo "exit $?"
    ```

## 4. Decision table

| Signal | Meaning | Action |
| --- | --- | --- |
| Tip has an exact tree twin in main | Content already in main | After a backup tag, the local ref may move to main |
| Containment 85 percent or more, no residual files | Absorbed | Drop |
| Commit only deletes files that main still has | Main contradicts the removal | Drop |
| Residual file MOVED or SAMENAME | Relocated | Compare at the new path before judging |
| Residual file DELETED in main history | Intentional removal | Drop |
| Residual file NEVER in main history | Real salvage candidate | Replay only that delta, by merge mode |
| Contamination labels above zero | Literal the scrub removed | Keep the redacted side; never replay |
| Generated file such as `LESSONS.md` | Rendered output | Regenerate through the pipeline |

## 5. Gotchas

* Git Bash path conversion: do not export `MSYS_NO_PATHCONV=1` for a whole session. It makes
  native Python receive `/c/...` paths, and repo hooks then fail with a bogus drive-root path.
  Prefix single `git show <ref>:<path>` commands only, because the colon triggers conversion.
* PowerShell: a helper function named `h` collides with the `Get-History` alias, and the parameter
  binding error echoed a secret passed as an argument. Use descriptive names and print
  fingerprints, never values.
* `git rev-parse --short=8 A B` fails; the option accepts one revision per call.
* Hook gates fail closed on a missing tool. Install the pinned linter into an existing global npm
  prefix with `--ignore-scripts`; never use `--no-verify`.
* A tree twin matches an exact snapshot only. A squash merge reads NEEDS-REANCHOR although the
  content landed (lesson `00f3e059181b`); confirm with containment before concluding anything.
* Patch parsing must track hunk state. With `-U0` each hunk header states how many lines follow, so
  file headers are recognised only outside a hunk. An added line whose content begins with two
  plus signs and a space appears in the diff as a line that starts with three plus signs and a
  space, exactly like a new-file header. A parser that treats every such line as a header
  silently drops it and misattributes the lines after it. Version 2 of the script counts hunk
  lines instead.
* Fail closed. Every git call aborts the run on an unexpected status, and a path counts as absent
  only when the target tree listing says so; otherwise an unreadable target would look like a
  repository where nothing exists and every commit would read as unique. The target and the
  repository's object format (SHA-1 or SHA-256) are validated up front.
* Containment is textual. Version 2 keeps line multiplicity (each target line satisfies at most
  one added line), but it does not keep block context: a statement that exists elsewhere in the
  target file still counts as present. Read the PARTIAL and mostly-absorbed rows before dropping.
* Read-only includes the object database. `git merge-tree --write-tree` stores the merged tree as
  new objects, so `classify` runs it in an object quarantine: a temporary object directory
  receives the writes and the repository is attached as an alternate. Git writes objects
  read-only, so the cleanup at exit must clear that attribute; a plain recursive delete leaves the
  directory behind on Windows (reproduced with a 60-file merge).
* A root commit has no parent: its base is the empty tree and its merge-tree result is reported as
  not applicable. An empty candidate list is a valid zero-candidate result: each mode prints its
  header and zero rows instead of failing.
* The residual mode guesses a relocated path from the first file with the same basename. Generic
  names such as `SKILL.md` collide, so resolve renames by hand (`git log --diff-filter=D --follow`
  or a search for the old skill name) before judging a SAMENAME row. A trial run found four such
  false mappings.
* The scratch scripts print contamination hit counts by label only. Never print matched values.

## 6. Script

Version 3, after two rounds of review fixes. Tested on throwaway repositories (a content line
shaped like a diff header, duplicated lines, a bad target, a SHA-256 repository, more than 14
residual rows, an object-database check with a negative control, temp-directory cleanup on a
60-file merge, a root commit and an empty list) and re-run against orama-system on 2026-10-23:
the `classify` output is identical to version 1, the `contain` percentages move by at most one
point on three large commits (duplicates now consume target lines), and the `residual` tally is
unchanged with every row printed. A full `classify` run left the repository's object count
unchanged.

```python
#!/usr/bin/env python3
"""Read-only triage of "patch-unique" commits against a rewritten main.

Why: after a history rewrite, `git cherry`, ahead/behind and merge-base cannot say whether a
branch's commits are missing from main or merely re-created under new SHAs. This tool answers
per commit, without touching any ref, index, working tree or the repository's object database:

  classify  per-file 3-way status (APPLIED / CLEAN / NEW / DELMAIN / DIVERGED), a
            `git merge-tree --write-tree` result, net effect vs main, and contamination-pattern
            hit COUNTS by label (never values). merge-tree writes the merged tree as new objects,
            so it runs in an object quarantine: a temporary object directory receives the writes
            and the repository is attached as a read-only alternate. The temporary directory is
            deleted on exit.
  contain   share of each commit's non-trivial added lines already present in main's copy of
            the same file (each target line can satisfy only one added line); deletions that
            main still contradicts; a verdict.
  residual  classifies the low-containment files: MOVED / SAMENAME / DELETED / NEVER / LOWPCT.

Every git failure aborts the run (exit 2); a path counts as absent only when the target tree
listing says so. A root commit is compared with the empty tree (its merge-tree result is n/a),
and an empty commit list prints headers with zero rows. Containment is textual: it keeps line
multiplicity but not block context.

Usage:  python reanchor_triage.py <repo> <classify|contain|residual> --list shas.txt
        [--target origin/main]        (needs git >= 2.38 for merge-tree --write-tree)
"""
import argparse
import atexit
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections import Counter, namedtuple

HOME = "Us" + "ers"  # keeps the literal home-directory token out of tracked text
PATTERNS = {
    "workstation-path": re.compile(r"(/%s/[A-Za-z][^/\s\"']*/|[A-Za-z]:\\%s\\[A-Za-z])" % (HOME, HOME)),
    "lan-ip": re.compile(r"\b(192\.168|10\.\d{1,3}|172\.(1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "token-like": re.compile(
        r"(?i)(bearer\s+[A-Za-z0-9_\-.]{20,}|sk_[a-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}"
        r"|(token|secret|password|api[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-.]{20,})"
    ),
}
HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")
OID_WIDTH = {"sha1": 40, "sha256": 64}
EMPTY_TREE = {  # built into git, so these resolve even though no such object is stored
    "sha1": "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
    "sha256": "6ef19b41225c5369f1c104d45d8d85efa9b057b53b14b4b9b939dd74decc5321",
}
Ctx = namedtuple("Ctx", "git target zero oid_re entries empty_tree qenv")


class GitError(RuntimeError):
    pass


def make_git(repo):
    def git(*args, ok=(0,), env=None):
        p = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", *args], capture_output=True, env=env)
        if p.returncode not in ok:
            err = p.stderr.decode("utf-8", "replace").strip()[:200]
            raise GitError(f"git {' '.join(args[:3])} failed (rc={p.returncode}): {err}")
        return p.returncode, p.stdout.decode("utf-8", "replace")

    return git


def force_rmtree(path):
    """Delete a directory tree even when it holds read-only files (git writes objects read-only)."""

    def fix(func, p, *_):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=fix)
    else:
        shutil.rmtree(path, onerror=fix)


def make_ctx(repo, target):
    git = make_git(repo)
    try:
        git("rev-parse", "--verify", "--quiet", f"{target}^{{commit}}")
    except GitError:
        raise GitError(f"target ref not found or not a commit: {target}") from None  # fail closed
    fmt = git("rev-parse", "--show-object-format")[1].strip()
    if fmt not in OID_WIDTH:
        raise GitError(f"unsupported object format: {fmt}")
    width = OID_WIDTH[fmt]
    entries = {}
    for ent in git("ls-tree", "-r", "-z", target)[1].split("\0"):
        if ent:
            meta, path = ent.split("\t", 1)
            _mode, kind, sha = meta.split()
            entries[path] = (kind, sha)
    objdir = git("rev-parse", "--path-format=absolute", "--git-path", "objects")[1].strip()
    qdir = tempfile.mkdtemp(prefix="triage-objects-")
    atexit.register(force_rmtree, qdir)
    qenv = dict(os.environ, GIT_OBJECT_DIRECTORY=qdir, GIT_ALTERNATE_OBJECT_DIRECTORIES=objdir)
    return Ctx(git, target, "0" * width, re.compile(r"[0-9a-f]{%d}" % width), entries, EMPTY_TREE[fmt], qenv)


def base_of(ctx, c):
    """The commit's first parent, or the empty tree for a root commit."""
    rc, _ = ctx.git("rev-parse", "--verify", "--quiet", f"{c}^", ok=(0, 1))
    return f"{c}^" if rc == 0 else ctx.empty_tree


def trivial(line):
    s = line.strip()
    return len(s) < 6 or re.fullmatch(r"[-=*_#`|>\s]+", s) is not None


def added_lines_by_file(ctx, c):
    """Return ({path: [added lines]}, [deleted paths]) for commit c versus its first parent.

    File headers are recognised only outside a hunk. Inside a hunk the -U0 counts say exactly
    how many '-' and '+' lines follow, so an added line whose content starts with '++ ' is
    kept as content instead of being mistaken for a header.
    """
    _, patch = ctx.git("diff", "-U0", "--no-color", "--no-renames", base_of(ctx, c), c)
    files, deleted, cur, old = {}, [], None, None
    rem_old = rem_new = 0
    for ln in patch.split("\n"):
        if rem_old or rem_new:
            if ln.startswith("+"):
                rem_new -= 1
                if cur is not None:
                    files[cur].append(ln[1:])
            elif ln.startswith("-"):
                rem_old -= 1
            continue
        m = HUNK.match(ln)
        if m:
            rem_old = int(m.group(1)) if m.group(1) is not None else 1
            rem_new = int(m.group(2)) if m.group(2) is not None else 1
        elif ln.startswith("--- "):
            old = ln[4:].split("\t")[0]
        elif ln.startswith("+++ "):
            new = ln[4:].split("\t")[0]
            if new == "/dev/null":
                deleted.append(old[2:] if old.startswith("a/") else old)
                cur = None
            else:
                cur = new[2:] if new.startswith("b/") else new
                files.setdefault(cur, [])
    return files, deleted


def target_lines(ctx, cache, path):
    """Counter of stripped lines in the target's copy of path, or None if it is not a file there."""
    ent = ctx.entries.get(path)
    if ent is None or ent[0] != "blob":
        return None
    if path not in cache:
        txt = ctx.git("show", f"{ctx.target}:{path}")[1]
        cache[path] = Counter(x.strip() for x in txt.split("\n"))
    return cache[path]


def contained(have, adds):
    """How many added lines are present in the target copy, each target line used once."""
    if have is None:
        return 0
    avail, hit = Counter(have), 0
    for a in adds:
        s = a.strip()
        if avail[s] > 0:
            avail[s] -= 1
            hit += 1
    return hit


def cmd_classify(ctx, commits):
    git = ctx.git
    print("sha      date       files | APPLIED CLEAN NEW DELMAIN DIVERGED | merge-tree | net-vs-main | hits | subject")
    for c in commits:
        date = git("log", "-1", "--format=%ad", "--date=short", c)[1].strip()
        subj = git("log", "-1", "--format=%s", c)[1].strip()[:44]
        base = base_of(ctx, c)
        _, raw = git("diff-tree", "-r", "--no-commit-id", "--raw", "-z", base, c)
        toks, i, n = raw.split("\0"), 0, 0
        k = dict.fromkeys(("APPLIED", "CLEAN", "NEW", "DELMAIN", "DIVERGED"), 0)
        while i < len(toks) - 1:
            if not toks[i].startswith(":"):
                i += 1
                continue
            parts = toks[i][1:].split()
            old_sha, new_sha, status = parts[2], parts[3], parts[4][0]
            path = toks[i + 1]
            i += 3 if status in "RC" else 2
            n += 1
            b_sha = None if old_sha == ctx.zero else old_sha
            post = None if new_sha == ctx.zero else new_sha
            ent = ctx.entries.get(path)
            cur = ent[1] if ent else None
            if cur == post:
                k["APPLIED"] += 1
            elif b_sha is None and cur is None:
                k["NEW"] += 1
            elif cur is None:
                k["DELMAIN"] += 1
            elif cur == b_sha:
                k["CLEAN"] += 1
            else:
                k["DIVERGED"] += 1
        if base == ctx.empty_tree:
            mt, net = "n/a (root)", "n/a"
        else:
            rc, out = git("merge-tree", "--write-tree", "--name-only", f"--merge-base={base}", ctx.target, c,
                          ok=(0, 1), env=ctx.qenv)
            lines = out.split("\n")
            tree = lines[0].strip()
            conflicts = []
            if rc == 1:
                for ln in lines[1:]:
                    if not ln.strip():
                        break
                    conflicts.append(ln.strip())
            mt = "clean" if rc == 0 else f"CONFLICT x{len(conflicts)}"
            net = "n/a"
            if ctx.oid_re.fullmatch(tree):
                changed = git("diff", "--name-only", ctx.target, tree, env=ctx.qenv)[1].split("\n")
                net = f"{len([x for x in changed if x])} files"
        files, _ = added_lines_by_file(ctx, c)
        added = [ln for adds in files.values() for ln in adds]
        hits = {lab: sum(1 for ln in added if rx.search(ln)) for lab, rx in PATTERNS.items()}
        hit_s = ",".join(f"{lab.split('-')[0]}={v}" for lab, v in hits.items() if v) or "none"
        print(f"{c[:8]} {date} {n:>5} | {k['APPLIED']:>7} {k['CLEAN']:>5} {k['NEW']:>3} {k['DELMAIN']:>7} {k['DIVERGED']:>8} | {mt:<14} | {net:<11} | {hit_s} | {subj}")


def cmd_contain(ctx, commits):
    cache = {}
    print("sha      added | in-main  pct | res<50% | deleted-but-in-main | verdict")
    for c in commits:
        files, deleted = added_lines_by_file(ctx, c)
        tot = hit = resid = 0
        for path, adds in files.items():
            nt = [a for a in adds if not trivial(a)]
            if not nt:
                continue
            h = contained(target_lines(ctx, cache, path), nt)
            tot, hit = tot + len(nt), hit + h
            resid += 1 if 100 * h / len(nt) < 50 else 0
        dim = sum(1 for p in deleted if target_lines(ctx, cache, p) is not None)
        pct = 100 * hit / tot if tot else 100.0
        if tot == 0:
            verdict = "main-contradicts" if dim else "no-content"
        elif pct >= 85:
            verdict = "ABSORBED" if not resid else "mostly absorbed"
        else:
            verdict = "PARTIAL" if pct >= 40 else "SALVAGE-CAND"
        print(f"{c[:8]} {tot:>6} | {hit:>6} {pct:>4.0f}% | {resid:>7} | {dim:>19} | {verdict}")


def cmd_residual(ctx, commits):
    git = ctx.git
    blob_path, by_base = {}, {}
    for p, (_kind, sha) in ctx.entries.items():
        blob_path.setdefault(sha, p)
        by_base.setdefault(p.rsplit("/", 1)[-1], []).append(p)
    cache, seen = {}, {}
    for c in commits:
        files, _ = added_lines_by_file(ctx, c)
        for path, adds in files.items():
            nt = [a for a in adds if not trivial(a)]
            if not nt:
                continue
            have = target_lines(ctx, cache, path)
            pct = 100 * contained(have, nt) / len(nt)
            if pct >= 50:
                continue
            post = git("rev-parse", f"{c}:{path}")[1].strip()
            base_name = path.rsplit("/", 1)[-1]
            if have is not None:
                cls, note = "LOWPCT", f"{int(pct)}%"
            elif post in blob_path:
                cls, note = "MOVED", blob_path[post]
            elif base_name in by_base:
                cls, note = "SAMENAME", by_base[base_name][0]
            else:
                deleted = git("log", ctx.target, "--diff-filter=D", "--format=%h", "-1", "--", path)[1].strip()
                ever = git("log", ctx.target, "--format=%h", "-1", "--", path)[1].strip()
                if deleted:
                    cls, note = "DELETED", f"deleted@{deleted}"
                elif ever:
                    cls, note = "DELETED?", f"in history@{ever}"
                else:
                    cls, note = "NEVER", "absent from target history"
            prev = seen.get(path)
            if prev is None or len(nt) > prev[1]:
                seen[path] = (cls, len(nt), note, c[:8])
    tally = Counter(v[0] for v in seen.values())
    print("residual files (deduped):", len(seen), dict(tally))
    for cls in ("NEVER", "DELETED?", "DELETED", "SAMENAME", "MOVED", "LOWPCT"):
        rows = sorted(((p, v) for p, v in seen.items() if v[0] == cls), key=lambda r: (-r[1][1], r[0]))
        if rows:
            print(f"\n== {cls} ({len(rows)})")
            for p, v in rows:
                print(f"  {v[1]:>4} lines  {p}   [{v[2]}] <- {v[3]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("mode", choices=("classify", "contain", "residual"))
    ap.add_argument("--list", required=True, help="file with one commit SHA per line")
    ap.add_argument("--target", default="origin/main")
    a = ap.parse_args()
    try:
        ctx = make_ctx(a.repo, a.target)
        shas = open(a.list, encoding="utf-8").read().split()
        order = ctx.git("rev-list", "--no-walk", "--date-order", "--reverse", *shas)[1] if shas else ""
        commits = order.split()
        {"classify": cmd_classify, "contain": cmd_contain, "residual": cmd_residual}[a.mode](ctx, commits)
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```
