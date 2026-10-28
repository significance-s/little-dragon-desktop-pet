"""Build reproducible Windows x64 bundles; never include personal runtime files."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "desktop_pet"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
APP_NAME = "LittleDragonPet"
VERSION = "0.2.1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_notices() -> Path:
    target = BUILD_DIR / "third-party"
    target.mkdir(parents=True, exist_ok=True)
    notices = {}
    for name in ("Pillow", "pystray", "six", "PyInstaller"):
        package = metadata.distribution(name)
        notices[name] = {
            "version": package.version,
            "source": f"https://pypi.org/project/{name}/{package.version}/",
        }
        for relative in package.files or ():
            lower = relative.name.lower()
            if "license" in lower or "copying" in lower:
                source = Path(package.locate_file(relative))
                if source.is_file():
                    destination = target / name / str(relative)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Python license file missing; cannot prepare release notices")
    shutil.copy2(python_license, target / "Python-LICENSE.txt")
    tcl_root = Path(sys.base_prefix) / "tcl"
    for source in tcl_root.glob("*/license.terms"):
        shutil.copy2(source, target / f"{source.parent.name}-license.terms")
    (target / "DEPENDENCIES.json").write_text(
        json.dumps({"Python": sys.version.split()[0], **notices}, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def build(mode: str) -> Path:
    if os.name != "nt" or struct.calcsize("P") != 8:
        raise RuntimeError("Build this target on 64-bit Windows Python.")
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Use the prepared project .venv to build, not global Python.")
    template = json.loads((APP_DIR / "config.example.json").read_text(encoding="utf-8"))
    if template.get("event_countdown") != {"enabled": False} or any(key in template for key in ("x", "y")):
        raise RuntimeError("Release defaults must not include personal dates, titles or coordinates.")
    assets = sorted((ROOT / "pic" / "gif").glob("*.apng"))
    if len(assets) != 7:
        raise RuntimeError("Expected exactly seven runtime APNG assets.")
    notices = collect_notices()
    command = [
        sys.executable, "-m", "PyInstaller", f"--{mode}", "--windowed",
        "--name", APP_NAME, "--noconfirm", "--clean", "--noupx",
        "--distpath", str(DIST_DIR / mode),
        "--workpath", str(BUILD_DIR / f"pyinstaller-{mode}"),
        "--specpath", str(BUILD_DIR / f"spec-{mode}"),
        "--paths", str(APP_DIR),
        "--hidden-import", "pystray._win32",
        "--exclude-module", "pystray._appindicator",
        "--exclude-module", "pystray._darwin",
        "--exclude-module", "pystray._xorg",
    ]
    for source, destination in (
        (APP_DIR / "config.example.json", "."),
        (ROOT / "LICENSE", "licenses"),
        (ROOT / "ASSETS.md", "licenses"),
        (notices, "licenses/third-party"),
        *((path, "pic/gif") for path in assets),
    ):
        command.extend(["--add-data", f"{source}{os.pathsep}{destination}"])
    command.append(str(APP_DIR / "launch.py"))
    subprocess.run(command, check=True, cwd=ROOT)
    executable = DIST_DIR / mode / (APP_NAME if mode == "onedir" else "") / f"{APP_NAME}.exe"
    if not executable.is_file():
        raise RuntimeError("Build completed without the expected EXE.")
    try:
        from scripts.audit_release import audit_executable
    except ModuleNotFoundError:
        from audit_release import audit_executable
    print(json.dumps(audit_executable(executable), ensure_ascii=False))
    return executable


def prepare_release(executable: Path) -> Path:
    release = DIST_DIR / "LittleDragonPet-Windows-x64"
    release.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, release / "小龙娘.exe")
    for name in ("LICENSE", "ASSETS.md", "LICENSE_STATUS.md", "CHANGELOG.md"):
        shutil.copy2(ROOT / name, release / name)
    shutil.copy2(ROOT / "docs" / "WINDOWS_RELEASE.md", release / "使用说明.md")
    notices = BUILD_DIR / "third-party"
    shutil.copytree(notices, release / "THIRD_PARTY_LICENSES", dirs_exist_ok=True)
    # pystray 未修改的 Python 源码随发行包提供，便于检查与用修改后的库重建。
    pystray = metadata.distribution("pystray")
    for relative in pystray.files or ():
        if relative.parts[0] == "pystray" and relative.suffix == ".py":
            destination = release / "THIRD_PARTY_SOURCES" / str(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pystray.locate_file(relative), destination)
    report = {
        "version": VERSION, "platform": "Windows x64", "format": "PyInstaller onefile",
        "Python": sys.version.split()[0], "PyInstaller": metadata.version("PyInstaller"),
        "exe_sha256": sha256(release / "小龙娘.exe"),
        "runtime_assets": {path.name: sha256(path) for path in sorted((ROOT / "pic/gif").glob("*.apng"))},
        "personal_data_included": False, "digitally_signed": False,
        "default_profile": "empty; countdown disabled; no question cards or daily history bundled",
    }
    (release / "BUILD_INFO.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    archive = DIST_DIR / "LittleDragonPet-Windows-x64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(release.rglob("*")):
            if path.is_file():
                zipped.write(path, str(Path(release.name) / path.relative_to(release)))
    return archive


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("onedir", "onefile"), default="onefile")
    args = parser.parse_args()
    executable = build(args.mode)
    print(f"Built: {executable}")
    if args.mode == "onefile":
        print(f"Release ZIP: {prepare_release(executable)}")


if __name__ == "__main__":
    main()
