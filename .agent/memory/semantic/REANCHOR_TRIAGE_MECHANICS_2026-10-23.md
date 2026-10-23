# Re-anchor triage mechanics (read-only): procedure, decision table and script

**Author:** claude-sonnet-5-5, written 2026-10-23 UTC. Reference companion to the session
chronicle of the same date; nothing existing is edited.
**Status:** reference. Every step is read-only on refs, index and working trees except the two
steps marked mutating (safety tags and the disposable worktree), which only add local refs.

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

5. Triage with the script in section 6. Run all three modes.

    ```bash
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

9. Commit with every hook active. Put the pinned markdown linter on PATH first; the message ends
   with the attribution line required by the organization's policy.

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
* In patch parsing, parse the file headers first. A content line that itself begins with `++`
  (for example inside a stored patch file) must still be counted; a naive filter drops it.
* The residual mode guesses a relocated path from the first file with the same basename. Generic
  names such as `SKILL.md` collide, so resolve renames by hand (`git log --diff-filter=D --follow`
  or a search for the old skill name) before judging a SAMENAME row. A trial run found four such
  false mappings.
* The scratch scripts print contamination hit counts by label only. Never print matched values.

## 6. Script

Verified on 2026-10-23 against orama-system: it reproduced the conflict counts, containment
percentages and the 36-file residual tally of the three earlier single-purpose scripts.

```python
#!/usr/bin/env python3
"""Read-only triage of "patch-unique" commits against a rewritten main.

Why: after a history rewrite, `git cherry`, ahead/behind and merge-base cannot say whether a
branch's commits are missing from main or merely re-created under new SHAs. This tool answers
per commit, without touching any ref, index or working tree:

  classify  per-file 3-way status (APPLIED / CLEAN / NEW / DELMAIN / DIVERGED), a read-only
            `git merge-tree --write-tree` result, net effect vs main, and contamination-pattern
            hit COUNTS by label (never values).
  contain   share of each commit's non-trivial added lines already present in main's copy of
            the same file; deletions that main still contradicts; a verdict.
  residual  classifies the low-containment files: MOVED / SAMENAME / DELETED / NEVER / LOWPCT.

Usage:  python reanchor_triage.py <repo> <classify|contain|residual> --list shas.txt
        [--target origin/main]        (needs git >= 2.38 for merge-tree --write-tree)
"""
import argparse
import re
import subprocess
import sys

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
ZERO = "0" * 40


def make_git(repo):
    def git(*args):
        p = subprocess.run(["git", "-C", repo, *args], capture_output=True)
        return p.returncode, p.stdout.decode("utf-8", "replace")

    return git


def trivial(line):
    s = line.strip()
    return len(s) < 6 or re.fullmatch(r"[-=*_#`|>\s]+", s) is not None


def main_blob_map(git, target):
    _, ls = git("ls-tree", "-r", "-z", target)
    out = {}
    for ent in ls.split("\0"):
        if ent:
            meta, path = ent.split("\t", 1)
            out[path] = meta.split()[2]
    return out


def added_lines_by_file(git, c):
    """Return ({path: [added lines]}, [deleted paths]) for commit c versus its parent."""
    _, patch = git("diff", "-U0", "--no-color", "--no-renames", f"{c}^", c)
    files, deleted, cur, old = {}, [], None, None
    for ln in patch.split("\n"):
        if ln.startswith("--- "):
            old = ln[4:]
        elif ln.startswith("+++ "):
            new = ln[4:]
            if new == "/dev/null":
                deleted.append(old[2:] if old.startswith("a/") else old)
                cur = None
            else:
                cur = new[2:] if new.startswith("b/") else new
                files.setdefault(cur, [])
        elif ln.startswith("+") and cur is not None:
            files[cur].append(ln[1:])
    return files, deleted


def cmd_classify(git, commits, target):
    main_map = main_blob_map(git, target)
    print("sha      date       files | APPLIED CLEAN NEW DELMAIN DIVERGED | merge-tree | net-vs-main | hits | subject")
    for c in commits:
        date = git("log", "-1", "--format=%ad", "--date=short", c)[1].strip()
        subj = git("log", "-1", "--format=%s", c)[1].strip()[:44]
        _, raw = git("diff-tree", "-r", "--no-commit-id", "--raw", "-z", f"{c}^", c)
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
            base = None if old_sha == ZERO else old_sha
            post = None if new_sha == ZERO else new_sha
            cur = main_map.get(path)
            if cur == post:
                k["APPLIED"] += 1
            elif base is None and cur is None:
                k["NEW"] += 1
            elif cur is None:
                k["DELMAIN"] += 1
            elif cur == base:
                k["CLEAN"] += 1
            else:
                k["DIVERGED"] += 1
        rc, out = git("merge-tree", "--write-tree", "--name-only", f"--merge-base={c}^", target, c)
        lines = out.split("\n")
        tree = lines[0].strip()
        conflicts = []
        if rc == 1:
            for ln in lines[1:]:
                if not ln.strip():
                    break
                conflicts.append(ln.strip())
        mt = "clean" if rc == 0 else (f"CONFLICT x{len(conflicts)}" if rc == 1 else f"error rc={rc}")
        net = "n/a"
        if rc in (0, 1) and re.fullmatch(r"[0-9a-f]{40}", tree):
            net = f"{len([x for x in git('diff', '--name-only', target, tree)[1].split(chr(10)) if x])} files"
        files, _ = added_lines_by_file(git, c)
        added = [ln for adds in files.values() for ln in adds]
        hits = {lab: sum(1 for ln in added if rx.search(ln)) for lab, rx in PATTERNS.items()}
        hit_s = ",".join(f"{lab.split('-')[0]}={v}" for lab, v in hits.items() if v) or "none"
        print(f"{c[:8]} {date} {n:>5} | {k['APPLIED']:>7} {k['CLEAN']:>5} {k['NEW']:>3} {k['DELMAIN']:>7} {k['DIVERGED']:>8} | {mt:<14} | {net:<11} | {hit_s} | {subj}")


def cur_lines(git, target, cache, path):
    if path not in cache:
        rc, txt = git("show", f"{target}:{path}")
        cache[path] = None if rc != 0 else {ln.strip() for ln in txt.split("\n")}
    return cache[path]


def cmd_contain(git, commits, target):
    cache = {}
    print("sha      added | in-main  pct | res<50% | deleted-but-in-main | verdict")
    for c in commits:
        files, deleted = added_lines_by_file(git, c)
        tot = hit = 0
        resid = 0
        for path, adds in files.items():
            nt = [a for a in adds if not trivial(a)]
            if not nt:
                continue
            have = cur_lines(git, target, cache, path)
            h = 0 if have is None else sum(1 for a in nt if a.strip() in have)
            tot, hit = tot + len(nt), hit + h
            resid += 1 if 100 * h / len(nt) < 50 else 0
        dim = sum(1 for p in deleted if cur_lines(git, target, cache, p) is not None)
        pct = 100 * hit / tot if tot else 100.0
        if tot == 0:
            verdict = "main-contradicts" if dim else "no-content"
        elif pct >= 85:
            verdict = "ABSORBED" if not resid else "mostly absorbed"
        else:
            verdict = "PARTIAL" if pct >= 40 else "SALVAGE-CAND"
        print(f"{c[:8]} {tot:>6} | {hit:>6} {pct:>4.0f}% | {resid:>7} | {dim:>19} | {verdict}")


def cmd_residual(git, commits, target):
    _, ls = git("ls-tree", "-r", "-z", target)
    blob_path, by_base = {}, {}
    for ent in ls.split("\0"):
        if ent:
            meta, p = ent.split("\t", 1)
            blob_path.setdefault(meta.split()[2], p)
            by_base.setdefault(p.rsplit("/", 1)[-1], []).append(p)
    cache, seen = {}, {}
    for c in commits:
        files, _ = added_lines_by_file(git, c)
        for path, adds in files.items():
            nt = [a for a in adds if not trivial(a)]
            if not nt:
                continue
            have = cur_lines(git, target, cache, path)
            pct = 0 if have is None else 100 * sum(1 for a in nt if a.strip() in have) / len(nt)
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
                deleted = git("log", target, "--diff-filter=D", "--format=%h", "-1", "--", path)[1].strip()
                ever = git("log", target, "--format=%h", "-1", "--", path)[1].strip()
                if deleted:
                    cls, note = "DELETED", f"deleted@{deleted}"
                elif ever:
                    cls, note = "DELETED?", f"in history@{ever}"
                else:
                    cls, note = "NEVER", "absent from target history"
            prev = seen.get(path)
            if prev is None or len(nt) > prev[1]:
                seen[path] = (cls, len(nt), note, c[:8])
    tally = {}
    for v in seen.values():
        tally[v[0]] = tally.get(v[0], 0) + 1
    print("residual files (deduped):", len(seen), tally)
    for cls in ("NEVER", "DELETED?", "DELETED", "SAMENAME", "MOVED", "LOWPCT"):
        rows = sorted(((p, v) for p, v in seen.items() if v[0] == cls), key=lambda r: -r[1][1])
        if rows:
            print(f"\n== {cls} ({len(rows)})")
            for p, v in rows[:14]:
                print(f"  {v[1]:>4} lines  {p}   [{v[2]}] <- {v[3]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("mode", choices=("classify", "contain", "residual"))
    ap.add_argument("--list", required=True, help="file with one commit SHA per line")
    ap.add_argument("--target", default="origin/main")
    a = ap.parse_args()
    git = make_git(a.repo)
    shas = open(a.list, encoding="utf-8").read().split()
    _, order = git("rev-list", "--no-walk", "--date-order", "--reverse", *shas)
    commits = order.split()
    {"classify": cmd_classify, "contain": cmd_contain, "residual": cmd_residual}[a.mode](git, commits, a.target)


if __name__ == "__main__":
    sys.exit(main())
```
