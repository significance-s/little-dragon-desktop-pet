from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


APP_DATA_NAME = "LittleDragonDesktopPet"
SOURCE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RuntimePaths:
    resource_root: Path
    assets: Path
    template: Path
    state_dir: Path
    frozen: bool

    @property
    def config(self) -> Path:
        return self.state_dir / "config.json"

    @property
    def data(self) -> Path:
        return self.state_dir / "data"

    @property
    def error_log(self) -> Path:
        return self.state_dir / "logs" / "startup.log"


def runtime_paths(
    *, source_dir: Path = SOURCE_DIR, frozen: bool | None = None,
    bundle_dir: Path | None = None, local_appdata: Path | None = None,
    data_dir: Path | None = None,
) -> RuntimePaths:
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if frozen:
        resource_root = bundle_dir or Path(getattr(sys, "_MEIPASS"))
        template = resource_root / "config.example.json"
    else:
        resource_root = source_dir.parent
        template = source_dir / "config.example.json"
    override = data_dir or os.environ.get("LITTLE_DRAGON_DATA_DIR")
    if override:
        state_dir = Path(override).expanduser().resolve()
    elif frozen:
        local_appdata = local_appdata or Path(
            os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        )
        state_dir = local_appdata / APP_DATA_NAME
    else:
        state_dir = source_dir
    return RuntimePaths(resource_root, resource_root / "pic" / "gif", template, state_dir, frozen)
