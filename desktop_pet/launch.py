"""Source and frozen entry point with errors, startup checks and packaging smoke tests."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import os
import sys
import traceback

from pet.runtime import runtime_paths


ERROR_LOG: Path | None = None


def report_error(details: str, show_popup: bool = True) -> None:
    error_log = ERROR_LOG or runtime_paths().error_log
    message = "小龙娘启动失败。"
    try:
        error_log.parent.mkdir(parents=True, exist_ok=True)
        with error_log.open("a", encoding="utf-8") as log:
            log.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n{details}\n")
        message += f"\n错误记录：\n{error_log}"
    except OSError:
        message += "\n无法写入错误日志，请检查数据目录的访问权限。"
    if sys.stderr is not None:
        print(details, file=sys.stderr)
    try:
        import tkinter as tk
        if tk._default_root is not None:
            tk._default_root.destroy()
        if show_popup:
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            try:
                messagebox.showerror("小龙娘启动失败", message, parent=root)
            finally:
                root.destroy()
    except Exception:
        pass


def diagnostic_info() -> dict:
    import PIL
    import pystray
    paths = runtime_paths()
    return {
        "frozen": paths.frozen,
        "executable": sys.executable,
        "resource_root": str(paths.resource_root),
        "state_dir": str(paths.state_dir),
        "pillow_module": str(PIL.__file__),
        "pystray_module": str(pystray.__file__),
    }


def check_startup() -> dict:
    import tkinter as tk
    from app import ASSET_DIR, load_config
    from pet.assets import AssetCatalog
    from pet.tray import TrayController, make_tray_image
    load_config()
    assets = AssetCatalog.discover(ASSET_DIR)
    assets.validate()
    root = tk.Tk()
    root.withdraw()
    try:
        tray = TrayController(root, make_tray_image(assets.files["idle"]), {})
        tray.start()
        try:
            root.update()
        finally:
            tray.stop()
    finally:
        root.destroy()
    return {"ok": True, "check": "config, seven animations, Tk and native tray", **diagnostic_info()}


def packaging_self_test() -> dict:
    from app import CONFIG_PATH, load_config, main as run_pet
    from pet.question_bank import push_question_bank
    from pet.question_panel import QuestionCardPanel
    from pet.study import StudySession
    config = dict(load_config())
    config.update(size=128, always_on_top=False, random_actions=False, start_hidden=True)
    config["event_countdown"] = {"enabled": False}
    checks = {}

    def ready(pet) -> None:
        pet.study_session = StudySession("packaging check", 2)
        pet._ensure_study_panel()
        pet.study_panel.withdraw()
        pet._update_study_panel()
        pet._schedule_study_tick()
        pet.set_state("work", return_to_idle=False)
        push_question_bank(pet.question_bridge.data_dir, {
            "set_id": "packaging-check", "title": "Packaging check",
            "questions": [{"id": "q1", "title": "Diagnostic only"}],
        })
        bank = pet.question_bridge.load_if_changed()
        if bank is None:
            raise RuntimeError("Question-card bank did not load")
        pet.question_panel = QuestionCardPanel(
            pet.root, bank, pet._save_question_state,
            pet.question_bridge.export_result,
        )
        pet.question_panel.hide()
        pet.question_panel.note_text.insert("1.0", "packaging check")
        pet.question_panel.save_button.invoke()
        pet.question_panel.status_buttons["done"].invoke()
        pet.question_panel.return_button.invoke()
        pet.open_calendar()
        pet.calendar_panel.note_text.insert("1.0", "Diagnostic review")
        pet.calendar_panel.done_var.set("2")
        if not pet.calendar_panel.save():
            raise RuntimeError("Calendar review did not save")
        pet.calendar_panel.hide()

        def finish() -> None:
            try:
                checks["study_tick"] = pet.study_session.remaining_seconds < 2
                checks["question_note_saved"] = bank.questions[0].note == "packaging check"
                checks["question_receipt"] = pet.question_bridge.outbox_path.is_file()
                daily = pet.journal.summary(pet.journal.today())
                checks["calendar_and_daily_summary"] = (
                    daily["focus_seconds"] > 0 and daily["done"] == 3
                    and daily["note"] == "Diagnostic review"
                )
                pet.set_state("wave")
                pet.set_size(160)
                checks["animation_and_resize"] = pet.size == 160 and bool(pet.label.image)
            except Exception:
                checks["error"] = traceback.format_exc()
            finally:
                pet.close()
        pet.root.after(1300, finish)

    run_pet(config_override=config, on_ready=ready)
    if checks.get("error") or not all(checks.get(key) for key in (
        "study_tick", "question_note_saved", "question_receipt", "animation_and_resize",
        "calendar_and_daily_summary",
    )):
        raise RuntimeError(f"Packaged smoke checks failed: {checks}")
    return {"ok": True, "self_test": checks, "config_persisted": CONFIG_PATH.is_file(),
            **diagnostic_info()}


def write_report(result: dict, report_file: Path | None) -> None:
    if report_file is not None:
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if sys.stdout is not None:
        print(json.dumps(result, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Little Dragon Desktop Pet")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--self-test", action="store_true")
    parser.add_argument("--data-dir", type=Path, help="Override runtime state directory")
    parser.add_argument("--report-file", type=Path, help="Write diagnostic JSON (including in windowed EXE)")
    args = parser.parse_args(argv)
    if args.data_dir is not None:
        os.environ["LITTLE_DRAGON_DATA_DIR"] = str(args.data_dir.resolve())
    try:
        if args.self_test:
            if args.data_dir is None:
                raise RuntimeError("--self-test requires an explicit --data-dir; never test on user data.")
            result = packaging_self_test()
        elif args.check:
            result = check_startup()
        else:
            from app import main as run_pet
            run_pet()
            return 0
        write_report(result, args.report_file)
        return 0
    except Exception:
        details = traceback.format_exc()
        report_error(details, show_popup=args.report_file is None)
        if args.report_file is not None:
            write_report({"ok": False, "error": details}, args.report_file)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
