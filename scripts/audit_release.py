"""Inspect our own built executable without running or extracting user files."""
from __future__ import annotations

import argparse
import json
import marshal
from pathlib import Path, PurePosixPath
import re
import types


PRIVATE_FILES = {
    "config.json", "question_inbox.json", "question_state.json", "question_outbox.json",
    "daily_journal.json", "startup.log",
}
USER_PATH = re.compile(r"[A-Za-z]:[/\\]+Users[/\\]+[^/\\\s]+", re.IGNORECASE)


def check_code(code: types.CodeType) -> int:
    if USER_PATH.search(code.co_filename):
        raise ValueError("A developer user path remains in packaged bytecode filenames")
    count = 1
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            count += check_code(value)
        elif isinstance(value, str) and USER_PATH.search(value):
            raise ValueError("A developer user path remains in packaged code constants")
    return count


def audit_executable(path: Path) -> dict:
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(path))
    resource_dir = path.parent / "_internal"
    names = list(archive.toc)
    if resource_dir.is_dir():
        names.extend(str(item.relative_to(resource_dir)) for item in resource_dir.rglob("*") if item.is_file())
    for name in names:
        normalized = name.replace("\\", "/")
        if PurePosixPath(normalized).name in PRIVATE_FILES or normalized.startswith(("data/", "returns/")):
            raise ValueError(f"Private runtime file bundled: {name}")
        if USER_PATH.search(normalized):
            raise ValueError("Absolute user path in bundled resource name")
    config_bytes = archive.extract("config.example.json") if "config.example.json" in archive.toc else (
        resource_dir / "config.example.json"
    ).read_bytes()
    config = json.loads(config_bytes.decode("utf-8"))
    if config.get("event_countdown") != {"enabled": False} or any(key in config for key in ("x", "y")):
        raise ValueError("Bundled defaults are not a clean generic profile")
    pyz = archive.open_embedded_archive("PYZ.pyz")
    modules = [name for name in pyz.toc if name == "app" or name == "pet" or name.startswith("pet.")]
    code_objects = check_code(marshal.loads(archive.extract("launch")))
    for name in modules:
        code = pyz.extract(name)
        if code is not None:
            code_objects += check_code(code)
    required = {"pet.calendar_panel", "pet.journal", "pet.question_panel", "pet.countdown", "pet.preferences"}
    if not required.issubset(modules):
        raise ValueError("A required application module is missing")
    return {
        "ok": True, "clean_defaults": True, "personal_runtime_files": False,
        "developer_user_paths": False, "checked_application_modules": len(modules) + 1,
        "checked_code_objects": code_objects,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_executable(args.executable), ensure_ascii=False, indent=2))
