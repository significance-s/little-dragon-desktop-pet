"""Install and run exclusively in this project's isolated virtual environment."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys


APP_DIR = Path(__file__).resolve().parent
VENV_DIR = APP_DIR.parent / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
REQUIREMENTS = APP_DIR / "requirements.txt"
SETUP_STAMP = VENV_DIR / ".pet-requirements.sha256"
DEPENDENCY_CHECK = r"""
import importlib.metadata, pathlib, re, site, sys
assert sys.prefix != sys.base_prefix, "An isolated venv is required"
assert pathlib.Path(sys.prefix).resolve() == pathlib.Path(sys.argv[1]).resolve(), "Wrong venv"
assert not site.ENABLE_USER_SITE, "User site-packages must be disabled"
assert (3,12) <= sys.version_info[:2] < (3,14), "Python 3.12 or 3.13 required"
import PIL, pystray, tkinter
def version_pair(value):
    match = re.match(r"(\d+)\.(\d+)", value)
    return tuple(map(int, match.groups())) if match else (-1,-1)
assert version_pair(PIL.__version__)[0] == 12, "Pillow>=12,<13 required"
assert (0,19) <= version_pair(importlib.metadata.version("pystray")) < (1,0), "pystray>=0.19,<1 required"
"""


def runtime_environment() -> dict[str, str]:
    env = os.environ.copy()
    # 不继承可能指向全局/用户包目录的 Python 环境设置。
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def venv_config_is_isolated() -> bool:
    try:
        text = (VENV_DIR / "pyvenv.cfg").read_text(encoding="utf-8")
    except OSError:
        return False
    fields = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            fields[key.strip().lower()] = value.strip().lower()
    return fields.get("include-system-site-packages") == "false"


def interpreter_ready(executable: Path) -> bool:
    if executable != VENV_PYTHON or not executable.is_file() or not venv_config_is_isolated():
        return False
    try:
        result = subprocess.run(
            [str(executable), "-I", "-c", DEPENDENCY_CHECK, str(VENV_DIR)],
            capture_output=True, timeout=20, env=runtime_environment(),
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def requirements_digest() -> str:
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()


def project_ready() -> bool:
    try:
        stamp_matches = SETUP_STAMP.read_text(encoding="ascii").strip() == requirements_digest()
    except OSError:
        return False
    return stamp_matches and interpreter_ready(VENV_PYTHON)


def prepare_venv(base_python: Path) -> Path:
    env = runtime_environment()
    if not VENV_PYTHON.is_file():
        print("Creating isolated project .venv...", flush=True)
        subprocess.run(
            [str(base_python), "-I", "-m", "venv", str(VENV_DIR)], check=True, env=env,
        )
    if not venv_config_is_isolated():
        raise RuntimeError("Existing .venv is not isolated. Rename it and run setup again.")
    subprocess.run(
        [str(VENV_PYTHON), "-I", "-m", "ensurepip", "--upgrade"], check=True, env=env,
    )
    print("Installing declared dependencies into project .venv...", flush=True)
    subprocess.run(
        [str(VENV_PYTHON), "-I", "-m", "pip", "--isolated", "install",
         "--no-user", "--disable-pip-version-check", "--retries", "1", "--timeout", "20",
         "-r", str(REQUIREMENTS)], check=True, env=env,
    )
    subprocess.run(
        [str(VENV_PYTHON), "-I", "-m", "pip", "--isolated", "check"], check=True, env=env,
    )
    if not interpreter_ready(VENV_PYTHON):
        raise RuntimeError("Project environment is not ready. Check Python's Tk support and setup errors.")
    # 只有安装和校验均成功才记为就绪；依赖文件修改后会再次安装。
    SETUP_STAMP.write_text(requirements_digest() + "\n", encoding="ascii")
    return VENV_PYTHON


def background_executable(executable: Path) -> Path:
    pythonw = executable.with_name("pythonw.exe")
    return pythonw if pythonw.is_file() else executable


def start_background(executable: Path) -> None:
    if executable != VENV_PYTHON:
        raise RuntimeError("Refusing to launch outside the project .venv.")
    subprocess.Popen(
        [str(background_executable(executable)), str(APP_DIR / "launch.py")],
        cwd=APP_DIR, env=runtime_environment(),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install and run the pet in project .venv.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="Read-only startup check of the prepared project environment.")
    mode.add_argument("--setup", action="store_true",
                      help="Create/repair project .venv and install dependencies, without starting a pet.")
    args = parser.parse_args(argv)
    if not (3, 12) <= sys.version_info[:2] < (3, 14):
        raise RuntimeError("Source edition requires Python 3.12 or 3.13 with Tcl/Tk.")
    if not project_ready():
        if args.check:
            print("Project .venv is not ready. Run run.bat --setup first.")
            return 1
        prepare_venv(Path(sys.executable))
    print(f"Using isolated project Python: {VENV_PYTHON}", flush=True)
    if args.check:
        return subprocess.run(
            [str(VENV_PYTHON), str(APP_DIR / "launch.py"), "--check"],
            cwd=APP_DIR, env=runtime_environment(),
        ).returncode
    if not args.setup:
        start_background(VENV_PYTHON)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Setup/startup failed: {exc}", file=sys.stderr)
        print("See README.md. No global Python packages were installed or borrowed.", file=sys.stderr)
        raise SystemExit(1)
