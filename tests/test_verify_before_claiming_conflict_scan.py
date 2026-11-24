"""The conflict-scan block in verify-before-claiming is identical in both repos and it works.

orama-system `docs/verify-before-claiming.md` and Perpetua-Tools
`.agent/protocols/verify-before-claiming.md` carry one block between the `conflict-scan:begin` and
`conflict-scan:end` comments, identical once the list indentation is removed. This file is the same
in both repositories and checks three things:

1. The block's SHA-256 equals PINNED_SHA256, so an edit that forgets the pin fails in that repo.
2. The block equals the sibling repository's block when that checkout is found next to this one.
   A pin alone cannot do this: editing one repo's block and its pin together passes that repo's own
   check while the other repo still passes against its old copy. The sibling comparison is the check
   that catches it. Set VERIFY_BLOCK_REQUIRE_SIBLING=1 to fail instead of skip when no sibling is
   found (for example before pushing a lockstep pair), and VERIFY_BLOCK_SIBLING_ROOT to name the
   sibling checkout when the directory layout is unusual. A CI job that sees only one repository
   cannot make this comparison; it skips, and the pin remains its only guard.
3. The block's two `git grep` commands, run in a throwaway repository, hit exactly the lines the
   prose says they hit, so the patterns are demonstrated and not read by eye.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ORAMA_DOC = "docs/verify-before-claiming.md"
PT_DOC = ".agent/protocols/verify-before-claiming.md"
# Update this value in BOTH repositories when the block changes; run this test to see the new hash.
PINNED_SHA256 = "3aec2ba7efb978da59e8c9089238c052d57cc201b72f03e5351050c03d7da387"
BLOCK = re.compile(
    r"^[ \t]*<!-- conflict-scan:begin -->[ \t]*\n(.*?)^[ \t]*<!-- conflict-scan:end -->",
    re.DOTALL | re.MULTILINE,
)
FENCE = re.compile(r"^```sh[ \t]*\n(.*?)^```", re.DOTALL | re.MULTILINE)
WORKING_TREE, INDEX = 0, 1
# Marker lines in the fixture below (opening, diff3 ancestor, separator, closing) and the two
# underline lines the scan reports for a reader to classify.
MARKER_LINES = {
    "deep/er/labelled.txt": (2, 4, 6, 8),
    "bare.txt": (2, 4, 6, 8),
    "crlf.txt": (2, 4, 6, 8),
    "sized.txt": (2, 4, 6),
    "notes.md": (4,),
    "title.py": (2,),
}


def _own_document() -> Path:
    """Return this repository's copy of the verify-before-claiming document."""
    found = [ROOT / name for name in (ORAMA_DOC, PT_DOC) if (ROOT / name).is_file()]
    assert len(found) == 1, f"expected exactly one verify-before-claiming document, found {found}"
    return found[0]


def _block(doc: Path) -> str:
    """Return the conflict-scan block of *doc* with its list indentation removed."""
    match = BLOCK.search(doc.read_text(encoding="utf-8"))
    assert match is not None, f"{doc} has no conflict-scan block"
    return textwrap.dedent(match.group(1)).strip("\n")


def _sibling_document() -> Path | None:
    """Locate the other repository's document, or None when no sibling checkout is found.

    VERIFY_BLOCK_SIBLING_ROOT names it directly. Otherwise the checkout is the single directory
    called ``orama-system`` or ``Perpetua-Tools`` directly under, or one level below, this
    checkout's parent or grandparent. Several matches are ambiguous and fail instead of guessing.
    """
    own_is_orama = _own_document() == ROOT / ORAMA_DOC
    name, doc = ("Perpetua-Tools", PT_DOC) if own_is_orama else ("orama-system", ORAMA_DOC)
    explicit = os.environ.get("VERIFY_BLOCK_SIBLING_ROOT", "").strip()
    if explicit:
        path = Path(explicit) / doc
        assert path.is_file(), f"VERIFY_BLOCK_SIBLING_ROOT has no {doc}: {path}"
        return path
    found: dict[Path, Path] = {}
    for base in (ROOT.parent, ROOT.parent.parent):
        for candidate in (base / name, *sorted(base.glob(f"*/{name}"))):
            if candidate.resolve() != ROOT and (candidate / doc).is_file():
                found[candidate.resolve()] = candidate / doc
    assert len(found) <= 1, f"ambiguous sibling checkouts, set VERIFY_BLOCK_SIBLING_ROOT: {sorted(found)}"
    return next(iter(found.values()), None)


def _commands() -> list[list[str]]:
    """Return the block's git commands as argument lists: working tree first, index second."""
    fence = FENCE.search(_block(_own_document()) + "\n```")
    assert fence is not None, "the conflict-scan block has no ```sh fence"
    lines = [line for line in fence.group(1).splitlines() if line.strip()]
    assert len(lines) == 2, lines
    commands = [shlex.split(line) for line in lines]
    assert commands[WORKING_TREE][:3] == ["git", "grep", "--untracked"], commands[WORKING_TREE]
    assert commands[INDEX][:3] == ["git", "grep", "--cached"], commands[INDEX]
    return commands


def _env(home: Path) -> dict[str, str]:
    """Return an environment that ignores the developer's git configuration."""
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "LC_ALL": "C",
    }


def _git(repo: Path, *args: str) -> None:
    """Run a git command in the repository with no user or system configuration."""
    subprocess.run(["git", *args], cwd=repo, env=_env(repo), check=True, capture_output=True)


def _scan(repo: Path, which: int, cwd: Path | None = None) -> list[str]:
    """Run one documented command and return its output lines (empty when git finds nothing)."""
    done = subprocess.run(
        _commands()[which], cwd=cwd or repo, env=_env(repo), capture_output=True, text=True
    )
    assert done.returncode in (0, 1), done.stderr
    return done.stdout.splitlines()


def _hits(lines: list[str], cwd: Path) -> set[tuple[str, int]]:
    """Return (path, line number) for every match line; context lines use '-' separators."""
    hits = set()
    for line in lines:
        found = re.match(r"^(.*?):(\d+):", line)
        if found:
            hits.add((os.path.normpath(cwd / found.group(1)), int(found.group(2))))
    return hits


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository whose staged files carry every marker shape the scan has to catch."""
    _git(tmp_path, "init", "-q", ".")
    _git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / "deep/er").mkdir(parents=True)
    files = {
        ".gitignore": b"ignored.txt\n",
        "deep/er/labelled.txt": b"a\n<<<<<<< HEAD\nx\n||||||| base\ny\n=======\nz\n>>>>>>> topic\n",
        "bare.txt": b"a\n<<<<<<<\nx\n|||||||\ny\n=======\nz\n>>>>>>>\n",
        "crlf.txt": b"a\r\n<<<<<<<\r\nx\r\n|||||||\r\ny\r\n=======\r\nz\r\n>>>>>>>\r\n",
        "sized.txt": b"a\n<<<<<<<<<< HEAD\nx\n==========\nz\n>>>>>>>>>> topic\n",
        "notes.md": b"# Title\n\nHeading text\n=======\n\nbody\n",
        "title.py": b'"""Title\n=======\nbody\n"""\n',
        "clean.txt": b"clean\n<<<<<< six only\ntext <<<<<<< mid line\n>>>>>>>x no space\n",
    }
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)
    _git(tmp_path, "add", ".")
    return tmp_path


def _expected(base: Path) -> set[tuple[str, int]]:
    """Return the (path, line) pairs the scan must report in the fixture, under *base*."""
    return {
        (os.path.normpath(base / name), number)
        for name, numbers in MARKER_LINES.items()
        for number in numbers
    }


def test_block_matches_the_pinned_hash() -> None:
    """An edited block fails here until the pin is updated, in both repositories."""
    digest = hashlib.sha256(_block(_own_document()).encode("utf-8")).hexdigest()
    assert digest == PINNED_SHA256, (
        "the conflict-scan block changed: copy it to the sibling repository, then set "
        f"PINNED_SHA256 = {digest!r} in this test in both repositories"
    )


def test_block_matches_the_sibling_repository() -> None:
    """The block is identical in the other repository: the check a pin alone cannot make."""
    sibling = _sibling_document()
    if sibling is None:
        if os.environ.get("VERIFY_BLOCK_REQUIRE_SIBLING") == "1":
            pytest.fail("VERIFY_BLOCK_REQUIRE_SIBLING=1 but no sibling checkout was found")
        pytest.skip("no sibling checkout found; the pinned hash still guards this repository")
    assert _block(sibling) == _block(_own_document()), (
        f"the conflict-scan block differs from the sibling copy in {sibling}: "
        "copy the changed block across, then update the pin in both repositories"
    )


@pytest.mark.parametrize("which", [WORKING_TREE, INDEX], ids=["working-tree", "index"])
def test_the_scan_reports_exactly_the_marker_lines_from_a_subdirectory(repo: Path, which: int) -> None:
    """Labelled, bare, diff3, CRLF and longer markers are all hit, and nothing else is."""
    here = repo / "deep/er"
    assert _hits(_scan(repo, which, cwd=here), here) == _expected(repo)


def test_ignored_files_are_not_searched(repo: Path) -> None:
    """The documented limit: an ignored file with markers is not reported by the working-tree scan."""
    (repo / "ignored.txt").write_bytes(b"<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> topic\n")
    hits = _hits(_scan(repo, WORKING_TREE), repo)
    assert hits == _expected(repo)
    assert not any(path.endswith("ignored.txt") for path, _ in hits)


def test_untracked_markers_are_found_only_in_the_working_tree_scan(repo: Path) -> None:
    """The working-tree scan reads untracked files; the index scan reads staged blobs only."""
    (repo / "untracked.txt").write_bytes(b"<<<<<<< HEAD\nu\n=======\nv\n>>>>>>> topic\n")
    assert any(line.startswith("untracked.txt:1:") for line in _scan(repo, WORKING_TREE))
    assert not any(line.startswith("untracked.txt") for line in _scan(repo, INDEX))


def test_a_marker_staged_then_removed_from_the_working_tree_is_found_by_the_index_scan(
    repo: Path,
) -> None:
    """A file staged with markers and then cleaned on disk still carries them in the index."""
    (repo / "bare.txt").write_bytes(b"resolved\n")
    assert not any(line.startswith("bare.txt") for line in _scan(repo, WORKING_TREE))
    assert any(line.startswith("bare.txt:2:") for line in _scan(repo, INDEX))


@pytest.mark.parametrize("which", [WORKING_TREE, INDEX], ids=["working-tree", "index"])
def test_an_underline_is_shown_with_the_title_line_above_it(repo: Path, which: int) -> None:
    """The -B1 context line lets a reader tell a Markdown or reST underline from a separator."""
    out = _scan(repo, which)
    assert "notes.md-3-Heading text" in out and "notes.md:4:=======" in out
    assert 'title.py-1-"""Title' in out and "title.py:2:=======" in out
