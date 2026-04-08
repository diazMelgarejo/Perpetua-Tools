#!/usr/bin/env python3
"""
setup_wizard.py
---------------
Idempotent installation wizard for Perplexity-Tools multi-agent orchestration.
"""

import os
import sys
import shutil
import platform
import subprocess
import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv, set_key
from orchestrator.key_helper import test_perplexity_key

ENV_PATH = Path(".env")
ALPHACLAW_URL = os.getenv("ALPHACLAW_URL", "http://127.0.0.1:18789")


def check_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def detect_ollama() -> tuple[bool, str | None]:
    if check_command("ollama"):
        try:
            result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return True, result.stdout.strip()
        except Exception:
            pass
    return False, None


def detect_lm_studio() -> bool:
    if platform.system() == "Darwin":
        return Path("/Applications/LM Studio.app").exists()
    return False


def detect_mlx() -> bool:
    if platform.system() != "Darwin":
        return False
    try:
        import mlx  # noqa: F401
        return True
    except ImportError:
        return False


def detect_python_env() -> dict:
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    in_venv = hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    return {"version": py_version, "in_venv": in_venv, "executable": sys.executable}


def detect_hardware_profile() -> str:
    system = platform.system()
    machine = platform.machine()
    if system == "Darwin" and machine == "arm64":
        return "mac-studio"
    if system == "Windows":
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "RTX 3080" in result.stdout:
                return "win-rtx3080"
        except Exception:
            pass
        return "win-generic"
    return "unknown"


def detect_alphaclaw() -> tuple[bool, bool]:
    installed = check_command("alphaclaw") or Path("node_modules/@chrysb/alphaclaw").exists()
    running = False
    try:
        import httpx

        response = httpx.get(f"{ALPHACLAW_URL}/health", timeout=1.0)
        running = response.status_code < 400
    except Exception:
        running = False
    return installed, running


def _resolve_perplexity_key() -> str | None:
    load_dotenv(ENV_PATH)
    key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    if key and test_perplexity_key(key):
        print("  ✓ PERPLEXITY_API_KEY already configured and valid")
        return key

    print("  No valid PERPLEXITY_API_KEY found.")
    print("  Get one at: https://www.perplexity.ai/settings/api")
    raw = input("  Paste your key (starts with pplx-, Enter to skip): ").strip()
    if not raw:
        print("  ⚠ Skipping key setup; cloud calls may be disabled.")
        return None

    while True:
        if not raw.startswith("pplx-"):
            raw = input("  Invalid prefix. Re-enter key (or Enter to skip): ").strip()
            if not raw:
                return None
            continue
        if test_perplexity_key(raw):
            ENV_PATH.touch(exist_ok=True)
            set_key(str(ENV_PATH), "PERPLEXITY_API_KEY", raw)
            os.environ["PERPLEXITY_API_KEY"] = raw
            print("  ✓ PERPLEXITY_API_KEY saved to .env")
            return raw
        raw = input("  Key validation failed. Re-enter key (or Enter to skip): ").strip()
        if not raw:
            return None


async def _wait_for_gateway(timeout: int = 30) -> bool:
    bar_width = 38
    print(f"\n  [alphaclaw] Waiting for gateway at {ALPHACLAW_URL}…")
    for elapsed in range(timeout + 1):
        filled = int(bar_width * elapsed / timeout)
        bar = "█" * filled + "░" * (bar_width - filled)
        pct = int(100 * elapsed / timeout)
        left = timeout - elapsed
        print(f"\r  [alphaclaw] [{bar}] {pct:3d}%  ({left:2d}s)  ", end="", flush=True)
        _, running = detect_alphaclaw()
        if running:
            print(f"\r  [alphaclaw] [{'█' * bar_width}] 100%  ✓ ready          ")
            return True
        if elapsed < timeout:
            await asyncio.sleep(1)
    print(f"\r  [alphaclaw] [{'░' * bar_width}] timed out after {timeout}s           ")
    return False


def _ensure_alphaclaw() -> None:
    installed, running = detect_alphaclaw()
    if installed and running:
        print("  ✓ alphaclaw found + gateway already responding")
        return

    if not installed:
        install = input("  alphaclaw not found. Install now? [Y/n]: ").strip().lower()
        if install == "n":
            print("  ⚠ Skipping alphaclaw install.")
            return

    bootstrap_script = Path("alphaclaw_bootstrap.py")
    if bootstrap_script.exists():
        result = subprocess.run([sys.executable, str(bootstrap_script), "--bootstrap"])
        if result.returncode == 0:
            return
        print("  ⚠ alphaclaw bootstrap script reported failure.")

    # Fallback if script is absent/fails: local direct start + wait
    if not installed:
        subprocess.run(["npm", "install", "@chrysb/alphaclaw@latest"])
    print("  Starting AlphaClaw fallback: npx alphaclaw start")
    subprocess.Popen(["npx", "alphaclaw", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    asyncio.run(_wait_for_gateway())


def run_wizard(args: argparse.Namespace) -> None:
    print("\n" + "=" * 60)
    print("    Perplexity-Tools Setup Wizard")
    print("    Idempotent Hardware-Aware Installation")
    print("=" * 60 + "\n")

    print("[0/5] Perplexity API credentials...\n")
    _resolve_perplexity_key()
    print()

    if not args.skip_scan:
        print("[1/5] Scanning for existing AI software...\n")
        ollama_exists, ollama_ver = detect_ollama()
        lm_studio_exists = detect_lm_studio()
        mlx_exists = detect_mlx()
        py_env = detect_python_env()
        print(f"  Python:     {py_env['version']} {'(venv)' if py_env['in_venv'] else '(system)'}")
        print(f"  Ollama:     {'✓ ' + ollama_ver if ollama_exists else '✗ not found'}")
        print(f"  LM Studio:  {'✓ detected' if lm_studio_exists else '✗ not found'}")
        print(f"  MLX:        {'✓ installed' if mlx_exists else '✗ not installed'}")
        print()

    print("[2/5] AlphaClaw gateway...\n")
    _ensure_alphaclaw()
    print()

    print("[3/5] Detecting hardware profile...\n")
    profile = detect_hardware_profile()
    print(f"  Detected profile: {profile}")
    print("  See hardware/SKILL.md for profile details.\n")

    print("[4/5] Recommended installation path:\n")
    if args.advanced:
        print("  → Advanced mode: showing distributed setup first.\n")
    else:
        if profile == "mac-studio":
            if detect_lm_studio():
                print("  ✓ LM Studio detected — easiest path for most Mac users.")
            elif detect_ollama()[0]:
                print("  ✓ Ollama detected — good path for Mac.")
            else:
                print("  → Priority 1 (Easiest): Install LM Studio")
                print("      Download: https://lmstudio.ai/")
        elif profile == "win-rtx3080":
            if detect_ollama()[0]:
                print("  ✓ Ollama detected on Windows.")
            else:
                print("  → Priority 1 (Easiest): Install Ollama for Windows")
                print("      Download: https://ollama.ai/download/windows")
        else:
            print("  → Install Ollama (cross-platform)")
            print("      https://ollama.ai/download")
        print()

    if args.advanced or input("Configure distributed multi-node setup? [y/N]: ").strip().lower() == "y":
        print("\n  ⚠️  Advanced: Distributed Mac + Windows Setup")
        print("     Next steps: configure routing and agent_launcher.py --configure")

    print("\n[5/5] Python dependencies + environment...\n")
    if Path("requirements.txt").exists():
        install_deps = input("  Install Python dependencies from requirements.txt? [Y/n]: ").strip().lower()
        if install_deps != "n":
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    env_example = Path(".env.example")
    env_file = Path(".env")
    if env_example.exists() and not env_file.exists():
        create_env = input("  Create .env from .env.example? [Y/n]: ").strip().lower()
        if create_env != "n":
            shutil.copy(env_example, env_file)
            print(f"  ✓ Created {env_file}")
    elif env_file.exists():
        print("  ✓ .env already exists.")

    print("\n" + "=" * 60)
    print("  Setup complete!")
    print("  Next: python agent_launcher.py")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Idempotent installation wizard for Perplexity-Tools")
    parser.add_argument("--skip-scan", action="store_true", help="Skip scanning for existing software")
    parser.add_argument("--advanced", action="store_true", help="Show advanced distributed setup options first")
    run_wizard(parser.parse_args())
