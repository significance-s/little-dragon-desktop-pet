import json
from pathlib import Path
import sys
import tkinter as tk
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from pet.assets import AssetCatalog
from pet.calendar_panel import CalendarPanel
from pet.journal import DailyJournal
from pet.question_bank import QuestionBankBridge, _write_json_atomic, push_question_bank
from pet.window import PetWindow


class IsolatedFiles(unittest.TestCase):
    def setUp(self):
        self.folder = APP_DIR / "tests/runtime_data/io_recovery" / uuid4().hex
        self.folder.mkdir(parents=True)

    def tearDown(self):
        for path in self.folder.rglob("*"):
            if path.is_file():
                path.unlink()


class AtomicWriteTests(IsolatedFiles):
    def test_success_fsyncs_and_cleans_temporary_file(self):
        path = self.folder / "state.json"
        with patch("pet.question_bank.os.fsync") as sync:
            _write_json_atomic(path, {"value": "新记录"})
        sync.assert_called_once()
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"value": "新记录"})
        self.assertEqual(list(self.folder.glob("*.tmp")), [])

    def test_replace_failure_preserves_existing_file_and_cleans_temp(self):
        path = self.folder / "state.json"
        path.write_text('{"value":"old"}', encoding="utf-8")
        with patch.object(Path, "replace", side_effect=PermissionError("synthetic replacement failure")):
            with self.assertRaises(PermissionError):
                _write_json_atomic(path, {"value": "new"})
        self.assertEqual(path.read_text(encoding="utf-8"), '{"value":"old"}')
        self.assertEqual(list(self.folder.glob("*.tmp")), [])

    def test_fsync_failure_does_not_replace_existing_file(self):
        path = self.folder / "state.json"
        path.write_text('{"value":"old"}', encoding="utf-8")
        with patch("pet.question_bank.os.fsync", side_effect=OSError("synthetic sync failure")):
            with self.assertRaises(OSError):
                _write_json_atomic(path, {"value": "new"})
        self.assertEqual(path.read_text(encoding="utf-8"), '{"value":"old"}')
        self.assertEqual(list(self.folder.glob("*.tmp")), [])

    def test_existing_temporary_file_is_not_deleted_on_create_failure(self):
        path = self.folder / "state.json"
        temporary = self.folder / ".state.json.collision.tmp"
        temporary.write_text("existing file", encoding="utf-8")
        with patch("pet.question_bank.uuid4") as token:
            token.return_value.hex = "collision"
            with self.assertRaises(FileExistsError):
                _write_json_atomic(path, {"value": "new"})
        self.assertEqual(temporary.read_text(encoding="utf-8"), "existing file")
        self.assertFalse(path.exists())


class BridgeRecoveryTests(IsolatedFiles):
    def test_blocked_data_path_does_not_raise_in_constructor(self):
        path = self.folder / "data"
        path.write_text("not a directory", encoding="utf-8")
        bridge = QuestionBankBridge(path)
        self.assertFalse(bridge.available)
        self.assertIn("暂不可用", bridge.last_error)
        self.assertIsNone(bridge.load_if_changed())
        with self.assertRaises(OSError):
            bridge.save_state()
        with self.assertRaises(OSError):
            bridge.export_result()
        self.assertEqual(path.read_text(encoding="utf-8"), "not a directory")

    def test_directory_can_recover_without_restarting_bridge(self):
        path = self.folder / "data"
        path.write_text("blocked", encoding="utf-8")
        bridge = QuestionBankBridge(path)
        path.unlink()
        push_question_bank(path, {"set_id": "synthetic", "title": "Synthetic",
                                  "questions": [{"id": "q1", "title": "Test"}]})
        self.assertIsNotNone(bridge.load_if_changed())
        self.assertTrue(bridge.available)
        self.assertIsNone(bridge.last_error)

    def test_stat_error_is_caught_and_same_inbox_can_retry(self):
        bridge = QuestionBankBridge(self.folder)
        push_question_bank(self.folder, {"set_id": "synthetic", "title": "Synthetic",
                                        "questions": [{"id": "q1", "title": "Test"}]})
        original = Path.stat

        def stat(path, *args, **kwargs):
            if path == bridge.inbox_path:
                raise PermissionError("synthetic stat failure")
            return original(path, *args, **kwargs)

        with patch.object(Path, "is_file", return_value=True), patch.object(Path, "stat", new=stat):
            self.assertIsNone(bridge.load_if_changed())
        self.assertFalse(bridge.available)
        self.assertIsNone(bridge._inbox_signature)
        self.assertIsNotNone(bridge.load_if_changed())
        self.assertTrue(bridge.available)

    def test_failed_state_write_does_not_consume_inbox_signature(self):
        bridge = QuestionBankBridge(self.folder)
        push_question_bank(self.folder, {"set_id": "synthetic", "title": "Synthetic",
                                        "questions": [{"id": "q1", "title": "Test"}]})
        with patch("pet.question_bank._write_json_atomic", side_effect=PermissionError("synthetic write failure")):
            self.assertIsNone(bridge.load_if_changed())
        self.assertIsNone(bridge._inbox_signature)
        self.assertFalse(bridge.available)
        self.assertIsNotNone(bridge.load_if_changed())
        self.assertTrue(bridge.state_path.is_file())


class JournalTransactionTests(IsolatedFiles):
    def test_failed_manual_write_keeps_memory_and_file_unchanged(self):
        journal = DailyJournal(self.folder / "daily.json")
        day = journal.today()
        journal.set_manual(day, 1, 0, "old review")
        journal.record_focus(3)
        original_file = journal.path.read_bytes()
        original_payload = json.dumps(journal.payload, sort_keys=True)
        with patch("pet.journal._write_json_atomic", side_effect=PermissionError("synthetic write failure")):
            with self.assertRaises(PermissionError):
                journal.set_manual(day, 9, 2, "unsaved draft")
        self.assertEqual(json.dumps(journal.payload, sort_keys=True), original_payload)
        self.assertEqual(journal.path.read_bytes(), original_file)
        self.assertEqual(journal.pending_seconds, 3)
        journal.set_manual(day, 2, 0, "retry succeeded")
        self.assertEqual(journal.summary(day)["focus_seconds"], 3)
        self.assertEqual(journal.summary(day)["note"], "retry succeeded")

    def test_stat_permission_error_enters_readonly(self):
        path = self.folder / "daily.json"
        original = Path.stat

        def stat(candidate, *args, **kwargs):
            if candidate == path:
                raise PermissionError("synthetic read denial")
            return original(candidate, *args, **kwargs)

        with patch.object(Path, "stat", new=stat):
            journal = DailyJournal(path)
        self.assertTrue(journal.read_only)
        with self.assertRaises(OSError):
            journal.save()


class CalendarRecoveryTests(IsolatedFiles):
    def setUp(self):
        super().setUp()
        self.root = tk.Tk()
        self.root.withdraw()
        self.journal = DailyJournal(self.folder / "daily.json")
        self.panel = CalendarPanel(self.root, self.journal)
        self.panel.window.withdraw()

    def tearDown(self):
        self.panel.destroy()
        self.root.destroy()
        super().tearDown()

    def draft(self):
        self.panel.note_text.insert("1.0", "keep this draft")
        self.panel.done_var.set("4")
        self.root.update()

    def test_readonly_locks_editors_but_navigation_and_close_work(self):
        self.panel.destroy()
        self.journal.path.write_text("broken", encoding="utf-8")
        self.journal = DailyJournal(self.journal.path)
        self.panel = CalendarPanel(self.root, self.journal)
        self.panel.window.withdraw()
        for widget in (self.panel.note_text, self.panel.done_entry, self.panel.stuck_entry, self.panel.save_button):
            self.assertEqual(str(widget.cget("state")), "disabled")
        self.panel.note_text.insert("1.0", "must not enter")
        self.root.update()
        self.assertFalse(self.panel.dirty)
        self.assertEqual(self.panel.note_text.get("1.0", "end-1c"), "")
        self.panel.change_month(1)
        self.panel.go_today()
        self.assertTrue(self.panel.hide())
        self.assertEqual(self.journal.path.read_text(encoding="utf-8"), "broken")

    def test_failed_save_retains_draft_and_cancelling_close_is_explicit(self):
        self.draft()
        with patch("pet.journal._write_json_atomic", side_effect=PermissionError("synthetic")):
            with patch("pet.calendar_panel.messagebox.askyesnocancel", return_value=None):
                self.assertFalse(self.panel.prepare_to_close())
        self.assertTrue(self.panel.dirty)
        self.assertEqual(self.panel.note_text.get("1.0", "end-1c"), "keep this draft")
        self.assertEqual(self.journal.summary(self.panel.selected)["note"], "")

    def test_failed_save_can_copy_draft_then_close_without_silent_save(self):
        self.draft()
        with patch("pet.journal._write_json_atomic", side_effect=PermissionError("synthetic")):
            with patch("pet.calendar_panel.messagebox.askyesnocancel", return_value=True):
                with patch.object(self.panel.window, "clipboard_clear"), patch.object(self.panel.window, "clipboard_append") as copied:
                    self.assertTrue(self.panel.prepare_to_close())
                    self.assertIn("keep this draft", copied.call_args.args[0])
        self.assertFalse(self.panel.dirty)
        self.assertEqual(self.journal.summary(self.panel.selected)["note"], "")

    def test_failed_save_can_explicitly_discard_and_hide(self):
        self.draft()
        with patch("pet.journal._write_json_atomic", side_effect=PermissionError("synthetic")):
            with patch("pet.calendar_panel.messagebox.askyesnocancel", return_value=False):
                self.assertTrue(self.panel.hide())
        self.assertFalse(self.panel.dirty)
        self.assertEqual(self.panel.note_text.get("1.0", "end-1c"), "")
        self.assertEqual(self.journal.summary(self.panel.selected)["done"], 0)

    def test_clipboard_failure_does_not_allow_copy_and_close(self):
        self.draft()
        with patch("pet.journal._write_json_atomic", side_effect=PermissionError("synthetic")):
            with patch("pet.calendar_panel.messagebox.askyesnocancel", return_value=True):
                with patch.object(self.panel.window, "clipboard_append", side_effect=tk.TclError("synthetic")):
                    self.assertFalse(self.panel.prepare_to_close())
        self.assertTrue(self.panel.dirty)

    def test_copy_summary_falls_back_to_raw_draft_for_invalid_input(self):
        self.draft()
        self.panel.done_var.set("-1")
        with patch.object(self.panel.window, "clipboard_clear"), patch.object(self.panel.window, "clipboard_append") as copied:
            self.panel.copy_summary()
        self.assertIn("-1", copied.call_args.args[0])
        self.assertIn("keep this draft", copied.call_args.args[0])
        self.assertTrue(self.panel.dirty)

    def test_discard_button_requires_confirmation(self):
        self.draft()
        with patch("pet.calendar_panel.messagebox.askyesno", return_value=False):
            self.panel.discard_draft()
        self.assertTrue(self.panel.dirty)
        with patch("pet.calendar_panel.messagebox.askyesno", return_value=True):
            self.panel.discard_draft()
        self.assertFalse(self.panel.dirty)
        self.assertEqual(self.panel.done_var.get(), "0")

    def test_successful_retry_saves_the_original_draft(self):
        self.draft()
        with patch("pet.journal._write_json_atomic", side_effect=PermissionError("synthetic")):
            self.assertFalse(self.panel.save())
        self.assertTrue(self.panel.save())
        self.assertEqual(self.journal.summary(self.panel.selected)["note"], "keep this draft")
        self.assertFalse(self.panel.dirty)


class PetRecoveryTests(IsolatedFiles):
    def setUp(self):
        super().setUp()
        self.root = tk.Tk()
        self.root.withdraw()
        self.pet = None

    def make_pet(self):
        self.pet = PetWindow(self.root, AssetCatalog.discover(APP_DIR.parent / "pic/gif"),
                             {"size": 128, "random_actions": False, "always_on_top": False},
                             self.folder / "config.json")
        return self.pet

    def tearDown(self):
        if self.pet is not None and not self.pet._closed:
            if self.pet.calendar_panel is not None:
                self.pet.calendar_panel.dirty = False
            self.pet.close()
        elif self.pet is None:
            self.root.destroy()
        super().tearDown()

    def test_bad_journal_allows_calendar_navigation_and_normal_exit(self):
        data = self.folder / "data"
        data.mkdir()
        path = data / "daily_journal.json"
        path.write_text("broken", encoding="utf-8")
        pet = self.make_pet()
        pet.open_calendar()
        self.assertTrue(pet.journal.read_only)
        self.assertFalse(pet.calendar_panel.dirty)
        self.assertTrue(pet.close())
        self.assertEqual(path.read_text(encoding="utf-8"), "broken")

    def test_unavailable_data_directory_does_not_break_basic_pet(self):
        (self.folder / "data").write_text("blocked", encoding="utf-8")
        pet = self.make_pet()
        self.root.update()
        self.assertFalse(pet.question_bridge.available)
        self.assertTrue(pet.journal.read_only)
        self.assertIsNotNone(pet.label.image)
        with patch("pet.window.messagebox.showwarning") as warning:
            pet.open_question_cards()
        warning.assert_called_once()
        self.assertTrue(pet.close())
        self.assertEqual((self.folder / "data").read_text(encoding="utf-8"), "blocked")

    def test_config_error_notifies_once_until_a_successful_retry(self):
        pet = self.make_pet()
        tray = Mock()
        pet.attach_tray(tray)
        with patch("pet.window._write_json_atomic", side_effect=PermissionError("synthetic")):
            self.assertFalse(pet._persist_config())
            self.assertFalse(pet._persist_config())
        self.assertEqual(tray.notify.call_count, 1)
        self.assertIsNotNone(pet.config_save_error)
        self.assertTrue(pet._persist_config())
        self.assertIsNone(pet.config_save_error)
        with patch("pet.window._write_json_atomic", side_effect=PermissionError("synthetic")):
            pet._persist_config()
        self.assertEqual(tray.notify.call_count, 2)

    def test_config_failure_exit_can_cancel_or_confirm(self):
        pet = self.make_pet()
        with patch("pet.window._write_json_atomic", side_effect=PermissionError("synthetic")):
            with patch("pet.window.messagebox.askokcancel", return_value=False):
                self.assertFalse(pet.close())
            self.assertFalse(pet._closed)
            with patch("pet.window.messagebox.askokcancel", return_value=True):
                self.assertTrue(pet.close())
        self.assertTrue(pet._closed)
        self.assertTrue(pet.close())  # Repeat exit is harmless.

    def test_tray_hide_respects_cancelled_draft_close(self):
        pet = self.make_pet()
        pet.open_calendar()
        with patch.object(pet.calendar_panel, "prepare_to_close", return_value=False):
            pet.hide_to_tray()
        self.assertFalse(pet.hidden_to_tray)

    def test_journal_flush_failure_also_requires_explicit_exit_choice(self):
        pet = self.make_pet()
        with patch.object(pet.journal, "save", side_effect=PermissionError("synthetic")):
            with patch("pet.window.messagebox.askokcancel", return_value=False):
                self.assertFalse(pet.close())
            with patch("pet.window.messagebox.askokcancel", return_value=True):
                self.assertTrue(pet.close())

    def test_question_state_failure_also_requires_explicit_exit_choice(self):
        pet = self.make_pet()
        push_question_bank(pet.question_bridge.data_dir, {
            "set_id": "synthetic-exit", "title": "Synthetic",
            "questions": [{"id": "q1", "title": "Test"}],
        })
        pet.question_bridge.load_if_changed()
        with patch.object(pet.question_bridge, "save_state", side_effect=PermissionError("synthetic")):
            with patch("pet.window.messagebox.askokcancel", return_value=False):
                self.assertFalse(pet.close())
            with patch("pet.window.messagebox.askokcancel", return_value=True):
                self.assertTrue(pet.close())


if __name__ == "__main__":
    unittest.main()
