from __future__ import annotations

import ctypes
import json
import tkinter as tk
from pathlib import Path
from collections.abc import Callable

from pet.assets import AssetCatalog
from pet.tray import TrayController, make_tray_image
from pet.window import PetWindow
from pet.runtime import runtime_paths
from pet.preferences import clean_retired_countdown
from pet.question_bank import _write_json_atomic


APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
RUNTIME_PATHS = runtime_paths()
CONFIG_PATH = RUNTIME_PATHS.config
CONFIG_TEMPLATE_PATH = RUNTIME_PATHS.template
ASSET_DIR = RUNTIME_PATHS.assets


def enable_windows_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def load_config(
    config_path: Path = CONFIG_PATH,
    template_path: Path = CONFIG_TEMPLATE_PATH,
) -> dict:
    # 干净仓库不提交个人 config.json，首次运行从公开模板加载。
    source = config_path if config_path.is_file() else template_path
    with source.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, dict):
        raise ValueError("桌宠配置 JSON 根节点必须是对象")
    cleaned = clean_retired_countdown(config)
    if cleaned != config and source == config_path:
        try:
            _write_json_atomic(config_path, cleaned)
        except OSError:
            # A read-only old config must not bring back a retired reminder.
            pass
    return cleaned


def main(
    config_override: dict | None = None,
    on_ready: Callable[[PetWindow], None] | None = None,
) -> None:
    enable_windows_dpi_awareness()
    config = load_config() if config_override is None else config_override
    assets = AssetCatalog.discover(ASSET_DIR)
    assets.validate()

    root = tk.Tk()
    pet = PetWindow(root, assets, config, CONFIG_PATH)
    tray = TrayController(
        root,
        make_tray_image(assets.files["idle"]),
        callbacks={
            "toggle_pet": pet.toggle_visibility,
            "start_study": pet.start_study_session,
            "show_study": pet._show_study_panel,
            "toggle_study_pause": pet._toggle_study_pause,
            "question_cards": pet.open_question_cards,
            "countdown": pet.show_event_countdown,
            "calendar": pet.open_calendar,
            "exit": pet.close,
        },
    )
    pet.attach_tray(tray)
    tray.start()
    pet.notify_storage_status()
    if bool(config.get("start_hidden", False)):
        pet.hide_to_tray()
    try:
        if on_ready is not None:
            on_ready(pet)
        root.mainloop()
    finally:
        try:
            if root.winfo_exists():
                pet.close()
        except tk.TclError:
            pass


if __name__ == "__main__":
    main()
