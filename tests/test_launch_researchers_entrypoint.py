import os
import subprocess
import sys
from pathlib import Path


def test_launch_researchers_imports_from_source_checkout(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    env = {
        **os.environ,
        "STATE_DIR": str(tmp_path / "state"),
    }

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {str(repo_root / 'scripts')!r}); "
                "import launch_researchers; "
                "import perpetua_tools.agent_launcher"
            ),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
