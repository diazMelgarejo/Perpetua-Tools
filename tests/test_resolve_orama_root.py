import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "scripts" / "resolve_orama_root.sh"
GENERIC_RESOLVER = ROOT / "scripts" / "git" / "resolve_sibling_git_repo.sh"


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def _make_orama_repo(path: Path) -> Path:
    (path / "bin" / "orama-system").mkdir(parents=True)
    (path / "bin" / "orama-system" / "SKILL.md").write_text("# orama\n", encoding="utf-8")
    _git_init(path)
    return path


def _make_pt_repo(path: Path) -> Path:
    (path / "scripts" / "git").mkdir(parents=True)
    shutil.copy2(RESOLVER, path / "scripts" / "resolve_orama_root.sh")
    shutil.copy2(GENERIC_RESOLVER, path / "scripts" / "git" / "resolve_sibling_git_repo.sh")
    _git_init(path)
    return path


def _run_resolver(pt_root: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    script = "source scripts/resolve_orama_root.sh && resolve_orama_root"
    run_env = os.environ.copy()
    for key in ("ORAMA_SYSTEM_PATH", "ORAMA_SYSTEM_ROOT", "ORAMA_ROOT"):
        run_env.pop(key, None)
    if env:
        run_env.update(env)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=pt_root,
        env=run_env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_env_override_honored(tmp_path: Path) -> None:
    pt = _make_pt_repo(tmp_path / "Perpetua-Tools")
    orama = _make_orama_repo(tmp_path / "orama-system")

    result = _run_resolver(pt, {"ORAMA_SYSTEM_PATH": str(orama)})

    assert result.returncode == 0
    assert result.stdout.strip() == str(orama)


def test_env_override_invalid_fails_closed(tmp_path: Path) -> None:
    pt = _make_pt_repo(tmp_path / "Perpetua-Tools")
    _make_orama_repo(tmp_path / "orama-system")
    invalid = tmp_path / "not-orama"
    invalid.mkdir()

    result = _run_resolver(pt, {"ORAMA_SYSTEM_PATH": str(invalid)})

    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_mother_dir_crawl_finds_orama_system(tmp_path: Path) -> None:
    mother = tmp_path / "OpenClaw"
    pt = _make_pt_repo(mother / "perplexity-api" / "Perpetua-Tools")
    orama = _make_orama_repo(mother / "orama-system")

    result = _run_resolver(pt)

    assert result.returncode == 0
    assert result.stdout.strip() == str(orama)


def test_stale_env_placeholder_allows_crawl_after_discard(tmp_path: Path) -> None:
    root = tmp_path / "home" / "workspace"
    pt = _make_pt_repo(root / "Perpetua-Tools")
    orama = _make_orama_repo(root / "orama-system")
    invalid = tmp_path / "openclaw-v1" / "orama-system"
    invalid.parent.mkdir(parents=True)

    stale_env = os.environ.copy()
    for key in ("ORAMA_SYSTEM_PATH", "ORAMA_SYSTEM_ROOT", "ORAMA_ROOT"):
        stale_env.pop(key, None)
    stale_env["ORAMA_SYSTEM_PATH"] = str(invalid)
    script = (
        "source scripts/resolve_orama_root.sh && "
        "discard_stale_orama_env_overrides && "
        "resolve_orama_root"
    )
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=pt,
        env=stale_env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(orama)


def test_no_orama_system_found_returns_failure(tmp_path: Path) -> None:
    pt = _make_pt_repo(tmp_path / "perplexity-api" / "Perpetua-Tools")

    result = _run_resolver(pt)

    assert result.returncode != 0
    assert result.stdout.strip() == ""
