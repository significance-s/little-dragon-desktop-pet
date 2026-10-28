from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tkinter as tk
import unittest
from unittest.mock import patch
from uuid import uuid4

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from app import load_config
from pet.assets import AssetCatalog
from pet.countdown import EventCountdown
from pet.preferences import clean_retired_countdown
from pet.study import StudySession
from pet.window import PetWindow


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        self.folder = APP_DIR / "tests/runtime_data/preferences" / uuid4().hex
        self.folder.mkdir(parents=True)
        self.path = self.folder / "config.json"
        self.fingerprint = hashlib.sha256(b"synthetic-retired").hexdigest()

    def tearDown(self):
        for path in self.folder.rglob("*"):
            if path.is_file():
                path.unlink()

    def test_retired_title_removed_not_just_hidden_and_other_fields_preserved(self):
        old = {"size": 320, "x": 123, "event_countdown": {
            "title": "synthetic- retired", "date": "2030-05-15", "enabled": True,
        }}
        self.path.write_text(json.dumps(old), encoding="utf-8")
        with patch("pet.preferences.RETIRED_TITLE_HASHES", {self.fingerprint}):
            cleaned = load_config(self.path, APP_DIR / "config.example.json")
        self.assertEqual(cleaned["event_countdown"], {"enabled": False})
        self.assertEqual(cleaned["size"], 320)
        self.assertEqual(cleaned["x"], 123)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), cleaned)
        self.assertEqual(clean_retired_countdown(cleaned), cleaned)

    def test_user_created_event_is_not_removed(self):
        config = {"event_countdown": {"title": "我的生日", "date": "2030-05-15", "enabled": True}}
        self.assertEqual(clean_retired_countdown(config), config)


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.folder = APP_DIR / "tests/runtime_data/menu" / uuid4().hex
        self.root = tk.Tk()
        self.root.withdraw()
        self.pet = PetWindow(
            self.root, AssetCatalog.discover(APP_DIR.parent / "pic/gif"),
            {"size": 128, "random_actions": False, "always_on_top": False},
            self.folder / "config.json",
        )

    def tearDown(self):
        self.pet.close()
        for path in self.folder.rglob("*"):
            if path.is_file():
                path.unlink()

    def test_compact_menu_order_and_nested_actions(self):
        menu = self.pet.menu
        labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
                  if menu.type(i) != "separator"]
        self.assertEqual(labels, [
            "小龙娘 · 桌面助手", "开始专注…", "学习日历与小结", "答题卡", "专注控制",
            "互动动作", "日期倒计时", "调整大小", "隐藏到托盘", "退出",
        ])
        self.assertEqual(menu.index("end") + 1, 13)
        self.assertEqual(self.pet.action_menu.index("end") + 1, 7)
        with patch.object(self.pet, "set_state") as action:
            self.pet.action_menu.invoke(1)
            action.assert_called_once_with("wave")
        self.assertEqual(menu.entrycget("隐藏到托盘", "accelerator"), "Esc")

    def test_focus_menu_tracks_pause_and_disabled_states(self):
        self.pet._refresh_menu_state()
        self.assertEqual(self.pet.focus_menu.entrycget(0, "state"), "disabled")
        self.pet.study_session = StudySession("Synthetic", 30)
        self.pet._refresh_menu_state()
        self.assertEqual(self.pet.focus_menu.entrycget(0, "state"), "normal")
        self.pet.study_session.paused = True
        self.pet._refresh_menu_state()
        self.assertEqual(self.pet.focus_menu.entrycget(0, "label"), "继续专注")

    def test_empty_event_stays_empty_after_save_and_restart(self):
        self.pet._persist_config()
        config = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["event_countdown"], {"enabled": False})
        self.assertFalse(self.pet.event_configured)
        self.assertIsNone(self.pet.countdown_panel)
        with patch("pet.window.simpledialog.askstring", return_value=None):
            self.pet.countdown_menu.invoke(0)
        self.assertFalse(self.pet.countdown_enabled.get())

    def test_clear_event_removes_name_date_and_panel(self):
        self.pet.event_countdown = EventCountdown("Synthetic event", date(2030, 5, 15))
        self.pet.event_configured = True
        self.pet.countdown_enabled.set(True)
        self.pet._update_event_countdown_panel()
        self.pet._persist_config()
        with patch("pet.window.messagebox.askyesno", return_value=False):
            self.pet._clear_event_countdown()
        self.assertTrue(self.pet.event_configured)
        with patch("pet.window.messagebox.askyesno", return_value=True):
            self.pet._clear_event_countdown()
        self.assertFalse(self.pet.event_configured)
        self.assertIsNone(self.pet.countdown_panel)
        config = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["event_countdown"], {"enabled": False})


if __name__ == "__main__":
    unittest.main()
