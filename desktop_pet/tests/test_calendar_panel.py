from datetime import date
from pathlib import Path
import sys
import tkinter as tk
import unittest
from unittest.mock import patch
from uuid import uuid4

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from pet.calendar_panel import CalendarPanel, shift_month
from pet.journal import DailyJournal
from pet.assets import AssetCatalog
from pet.window import PetWindow
from pet.study import StudySession


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.path = APP_DIR / "tests/runtime_data/calendar" / f"{uuid4().hex}.json"
        self.root = tk.Tk()
        self.root.withdraw()
        self.journal = DailyJournal(self.path, today=lambda: date(2028, 2, 29))
        self.panel = CalendarPanel(self.root, self.journal)
        self.root.update()

    def tearDown(self):
        if self.panel.window.winfo_exists():
            self.panel.destroy()
        self.root.destroy()
        self.path.unlink(missing_ok=True)

    def test_leap_day_month_navigation_and_today(self):
        self.assertEqual(shift_month(2028, 1, -1), (2027, 12))
        self.assertEqual(shift_month(2028, 12, 1), (2029, 1))
        self.assertEqual(shift_month(1, 1, -1), (1, 1))
        enabled = [b for b in self.panel.day_buttons if str(b["state"]) == "normal"]
        self.assertEqual(len(enabled), 29)
        self.panel.change_month(1)
        self.assertEqual(self.panel.month, 3)
        self.panel.go_today()
        self.assertEqual(self.panel.selected, date(2028, 2, 29))

    def test_manual_review_autosave_and_summary_copy(self):
        self.panel.done_var.set("3")
        self.panel.stuck_var.set("1")
        self.panel.note_text.insert("1.0", "Synthetic review")
        self.root.update()
        self.panel.select_day(date(2028, 2, 28))
        self.assertEqual(self.journal.summary(date(2028, 2, 29))["done"], 3)
        self.panel.go_today()
        self.panel.copy_button.invoke()
        self.assertIn("Synthetic review", self.root.clipboard_get())
        self.panel.hide()
        self.assertEqual(self.panel.window.state(), "withdrawn")

    def test_bad_input_prevents_silent_loss_on_day_change(self):
        self.panel.done_var.set("-1")
        self.panel.select_day(date(2028, 3, 1))
        self.assertEqual(self.panel.selected, date(2028, 2, 29))
        self.assertIn("未保存", self.panel.feedback_var.get())

    def test_controls_fit_at_normal_and_high_dpi(self):
        for scaling in (1.333, 2.0):
            self.panel.destroy()
            self.root.tk.call("tk", "scaling", scaling)
            self.panel = CalendarPanel(self.root, self.journal)
            self.root.update()
            window = self.panel.window
            for widget in (self.panel.note_text, self.panel.done_entry, self.panel.stuck_entry,
                           self.panel.save_button, self.panel.copy_button, self.panel.today_button,
                           *self.panel.day_buttons):
                self.assertTrue(widget.winfo_ismapped())
                self.assertLessEqual(widget.winfo_rooty() - window.winfo_rooty()
                                     + widget.winfo_height(), window.winfo_height())
                self.assertLessEqual(widget.winfo_rootx() - window.winfo_rootx()
                                     + widget.winfo_width(), window.winfo_width())


class JournalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.folder = APP_DIR / "tests/runtime_data/integration" / uuid4().hex
        self.root = tk.Tk()
        assets = AssetCatalog.discover(APP_DIR.parent / "pic/gif")
        self.pet = PetWindow(self.root, assets,
                             {"size": 128, "random_actions": False, "always_on_top": False},
                             self.folder / "config.json")

    def tearDown(self):
        self.pet.close()
        for path in self.folder.rglob("*"):
            if path.is_file():
                path.unlink()

    def test_clean_start_has_no_personal_countdown_or_bank(self):
        self.assertFalse(self.pet.countdown_enabled.get())
        self.assertIsNone(self.pet.countdown_panel)
        self.assertIsNone(self.pet.question_bridge.bank)
        self.assertFalse(self.pet.question_bridge.inbox_path.exists())
        self.assertEqual(self.pet.journal.payload["days"], {})

    def test_pause_finish_and_close_flush_actual_focus(self):
        self.pet.study_session = StudySession("Synthetic", 100)
        self.pet._study_tick()
        self.pet._toggle_study_pause()
        self.root.after_cancel(self.pet.study_job)
        self.pet._study_tick()
        self.assertEqual(self.pet.journal.summary(self.pet.journal.today())["focus_seconds"], 1)
        with patch.object(self.root, "bell"):
            self.pet._finish_study(True)
            self.pet._finish_study(True)
        item = self.pet.journal.summary(self.pet.journal.today())
        self.assertEqual(item["sessions"], 1)
        self.assertEqual(item["focus_seconds"], 1)
        self.pet.open_calendar()
        self.assertIsNotNone(self.pet.calendar_panel)


if __name__ == "__main__":
    unittest.main()
