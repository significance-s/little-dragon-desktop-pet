from datetime import date, datetime
from pathlib import Path
import json
import sys
import tkinter as tk
import unittest
from unittest.mock import patch


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from pet.assets import AssetCatalog  # noqa: E402
from pet.countdown import (  # noqa: E402
    CountdownPanel, EventCountdown, SHANGHAI_TIMEZONE,
    countdown_panel_position, shanghai_today,
)
from pet.window import PetWindow  # noqa: E402


class CountdownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event = EventCountdown.parse("测试目标", "2030-05-15")

    def test_generic_target_date_and_days(self) -> None:
        self.assertEqual(self.event.target_date, date(2030, 5, 15))
        self.assertEqual(self.event.remaining_days(date(2030, 3, 22)), 54)
        self.assertEqual(self.event.status_text(date(2030, 3, 22)), "还剩 54 天")
        self.assertEqual(self.event.status_text(date(2030, 5, 14)), "还剩 1 天")
        self.assertEqual(self.event.status_text(date(2030, 5, 15)), "就是今天！")
        self.assertEqual(self.event.status_text(date(2030, 5, 16)), "已过去 1 天")

    def test_calendar_days_across_leap_day_and_year(self) -> None:
        event = EventCountdown.parse("测试", "2028-03-01")
        self.assertEqual(event.remaining_days(date(2028, 2, 28)), 2)
        event = EventCountdown.parse("跨年", "2027-01-01")
        self.assertEqual(event.remaining_days(date(2026, 12, 31)), 1)

    def test_shanghai_timezone_is_explicit(self) -> None:
        with patch("pet.countdown.datetime") as clock:
            clock.now.return_value = datetime(2030, 3, 22, 0, 1, tzinfo=SHANGHAI_TIMEZONE)
            self.assertEqual(shanghai_today(), date(2030, 3, 22))
            clock.now.assert_called_once_with(SHANGHAI_TIMEZONE)

    def test_validation_and_round_trip(self) -> None:
        for text in ("2026-02-29", "2026-13-05", "5.15", "20300515", ""):
            with self.subTest(text=text), self.assertRaises(ValueError):
                EventCountdown.parse("测试", text)
        for title in (" ", "名" * 81):
            with self.assertRaises(ValueError):
                EventCountdown.parse(title, "2030-05-15")
        with self.assertRaises(ValueError):
            EventCountdown.from_config({"date": None})
        restored = EventCountdown.from_config(self.event.to_config(False))
        self.assertEqual(restored, self.event)

    def test_panel_placement_below_above_and_offscreen(self) -> None:
        self.assertEqual(countdown_panel_position(100, 100, 512, 1920, 1080, 320, 160),
                         (196, 620))
        self.assertEqual(countdown_panel_position(100, 700, 512, 1920, 1080, 320, 160),
                         (196, 532))
        for x, y, size in ((-500, -500, 128), (4000, 2000, 2048), (100, 100, 2048)):
            panel_x, panel_y = countdown_panel_position(x, y, size, 1920, 1080, 320, 160)
            self.assertGreaterEqual(panel_x, 0)
            self.assertGreaterEqual(panel_y, 0)
            self.assertLessEqual(panel_x + 320, 1920)
            self.assertLessEqual(panel_y + 160, 1080)


class CountdownPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self) -> None:
        self.root.destroy()

    def test_panel_content_and_dpi(self) -> None:
        for scaling in (1.333, 2.0):
            self.root.tk.call("tk", "scaling", scaling)
            panel = CountdownPanel(
                self.root, EventCountdown.parse("测试目标", "2030-05-15"), always_on_top=False,
                on_edit=lambda: None, on_hide=lambda: None,
                on_press=lambda e: None, on_drag=lambda e: None, on_release=lambda e: None,
            )
            panel.update(date(2030, 3, 22))
            panel.position(100, 100, 512)
            panel.show()
            self.root.update()
            self.assertEqual(panel.days_var.get(), "还剩 54 天")
            self.assertIn("2030.05.15", panel.date_var.get())
            for widget in (panel.title_label, panel.days_label, panel.date_label,
                           panel.edit_button, panel.hide_button):
                self.assertTrue(widget.winfo_ismapped())
                self.assertLessEqual(widget.winfo_rooty() - panel.window.winfo_rooty()
                                     + widget.winfo_height(), panel.window.winfo_height())
                self.assertLessEqual(widget.winfo_rootx() - panel.window.winfo_rootx()
                                     + widget.winfo_width(), panel.window.winfo_width())
            panel.hide()
            self.root.update()
            self.assertEqual(panel.window.state(), "withdrawn")
            panel.window.destroy()


class CountdownIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        # Windows 受限令牌下 tempfile 的 0700 目录可能无法重新访问，
        # 使用继承项目 ACL 的隔离测试目录，不接触真实配置/答题数据。
        self.test_dir = APP_DIR / "tests" / "runtime_data" / "countdown"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.test_dir / "config.json"
        self.root = tk.Tk()
        self.root.tk.call("tk", "scaling", 1.333)
        self.config = {"size": 128, "x": 100, "y": 100, "random_actions": False,
                       "always_on_top": False,
                       "event_countdown": {"title": "测试目标", "date": "2030-05-15", "enabled": True}}
        self.assets = AssetCatalog.discover(APP_DIR.parent / "pic" / "gif")
        self.pet = PetWindow(self.root, self.assets, self.config, self.config_path)
        self.root.update()

    def tearDown(self) -> None:
        self.pet.close()
        self.config_path.unlink(missing_ok=True)

    def test_default_visible_hide_restore_and_disable_persist(self) -> None:
        self.assertIsNotNone(self.pet.countdown_panel)
        panel = self.pet.countdown_panel
        self.assertEqual(panel.window.state(), "normal")
        self.pet.hide_to_tray()
        self.root.update()
        self.assertEqual(panel.window.state(), "withdrawn")
        self.pet._refresh_event_countdown()
        self.assertEqual(panel.window.state(), "withdrawn")
        self.pet.show_pet()
        self.root.update()
        self.assertEqual(panel.window.state(), "normal")
        self.pet._hide_event_countdown()
        self.pet.hide_to_tray()
        self.pet.show_pet()
        self.assertEqual(panel.window.state(), "withdrawn")
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertFalse(config["event_countdown"]["enabled"])
        self.assertEqual(config["event_countdown"]["date"], "2030-05-15")
        self.pet.show_event_countdown()
        self.root.update()
        self.assertEqual(panel.window.state(), "normal")

    def test_drag_resize_and_date_edit(self) -> None:
        class Pointer:
            x_root = 150
            y_root = 170

        panel = self.pet.countdown_panel
        old_x, old_y = panel.window.winfo_x(), panel.window.winfo_y()
        self.pet._on_study_press(Pointer())
        pointer = Pointer()
        pointer.x_root += 40
        pointer.y_root += 50
        self.pet._on_study_drag(pointer)
        self.pet._on_study_release(pointer)
        self.root.update()
        self.assertEqual(panel.window.winfo_x(), old_x + 40)
        self.assertEqual(panel.window.winfo_y(), old_y + 50)
        self.pet.set_size(260)
        self.root.update()
        self.assertEqual(panel.window.winfo_y(), self.root.winfo_y() + 260 + 8)
        with patch("pet.window.simpledialog.askstring", side_effect=["训练赛", "2027-01-01"]):
            self.pet._edit_event_countdown()
        self.assertEqual(self.pet.event_countdown.title, "训练赛")
        self.assertEqual(self.pet.event_countdown.target_date, date(2027, 1, 1))
        old_event = self.pet.event_countdown
        with patch("pet.window.simpledialog.askstring", side_effect=["错误", "12.5"]), \
                patch("pet.window.messagebox.showerror") as error:
            self.pet._edit_event_countdown()
        error.assert_called_once()
        self.assertEqual(self.pet.event_countdown, old_event)

    def test_refresh_recalculates_across_midnight_and_cancelled_edit(self) -> None:
        with patch("pet.countdown.shanghai_today", return_value=date(2030, 5, 14)):
            self.pet._refresh_event_countdown()
        self.assertEqual(self.pet.countdown_panel.days_var.get(), "还剩 1 天")
        with patch("pet.countdown.shanghai_today", return_value=date(2030, 5, 15)):
            self.pet._refresh_event_countdown()
        self.assertEqual(self.pet.countdown_panel.days_var.get(), "就是今天！")
        old_event = self.pet.event_countdown
        with patch("pet.window.simpledialog.askstring", side_effect=["未保存", None]):
            self.pet._edit_event_countdown()
        self.assertEqual(self.pet.event_countdown, old_event)

    def test_saved_disabled_setting_survives_restart(self) -> None:
        self.pet._hide_event_countdown()
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.pet.close()
        self.root = tk.Tk()
        self.pet = PetWindow(self.root, self.assets, saved, self.config_path)
        self.root.update()
        self.assertFalse(self.pet.countdown_enabled.get())
        self.assertIsNone(self.pet.countdown_panel)


if __name__ == "__main__":
    unittest.main()
