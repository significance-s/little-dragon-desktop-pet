from datetime import date
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from pet.journal import DailyJournal
from pet.question_bank import QuestionBank


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.path = APP_DIR / "tests/runtime_data/journal" / f"{uuid4().hex}.json"
        self.current_day = date(2028, 2, 28)
        self.journal = DailyJournal(self.path, today=lambda: self.current_day)
        self.bank = QuestionBank.from_dict({
            "set_id": "test-only", "title": "Synthetic",
            "questions": [{"id": "q1", "title": "Test one"}, {"id": "q2", "title": "Test two"}],
        })

    def tearDown(self):
        self.path.unlink(missing_ok=True)
        self.path.with_suffix(".json.tmp").unlink(missing_ok=True)

    def test_empty_start_has_no_history_or_file(self):
        self.assertEqual(self.journal.summary(self.current_day)["done"], 0)
        self.assertEqual(self.journal.payload["days"], {})
        self.assertFalse(self.path.exists())

    def test_focus_crosses_days_and_persists(self):
        self.journal.record_focus(20)
        self.current_day = date(2028, 2, 29)
        self.journal.record_focus(5)
        self.journal.save()
        restored = DailyJournal(self.path)
        self.assertEqual(restored.summary(date(2028, 2, 28))["focus_seconds"], 20)
        self.assertEqual(restored.summary(self.current_day)["focus_seconds"], 5)

    def test_questions_are_deduplicated_and_status_corrections_replace(self):
        self.journal.prime_bank(self.bank)
        self.bank.questions[0].status = "done"
        for _ in range(3):
            self.journal.record_bank(self.bank)
        self.assertEqual(self.journal.summary(self.current_day)["done"], 1)
        self.bank.questions[0].status = "stuck"
        self.bank.questions[0].note = "Synthetic blocker"
        self.journal.record_bank(self.bank)
        item = self.journal.summary(self.current_day)
        self.assertEqual(item["done"], 0)
        self.assertEqual(item["stuck"], 1)
        self.assertIn("Synthetic blocker", self.journal.markdown(self.current_day))

    def test_import_or_next_day_reopen_does_not_count_as_new_work(self):
        self.bank.questions[0].status = "done"
        self.journal.prime_bank(self.bank)
        self.journal.record_bank(self.bank)
        self.assertEqual(self.journal.summary(self.current_day)["done"], 0)
        self.bank.questions[1].status = "done"
        self.journal.record_bank(self.bank)
        self.current_day = date(2028, 2, 29)
        restored = DailyJournal(self.path, today=lambda: self.current_day)
        restored.record_bank(self.bank)
        self.assertEqual(restored.summary(self.current_day)["done"], 0)
        self.assertEqual(restored.summary(date(2028, 2, 28))["done"], 1)

    def test_manual_counts_and_notes_do_not_accumulate_on_repeated_save(self):
        for _ in range(3):
            self.journal.set_manual(self.current_day, 3, 2, "Synthetic review")
        item = self.journal.summary(self.current_day)
        self.assertEqual((item["done"], item["stuck"]), (3, 2))
        self.assertTrue(self.journal.has_activity(self.current_day))
        self.assertIn("Synthetic review", self.journal.markdown(self.current_day))
        with self.assertRaises(ValueError):
            self.journal.set_manual(self.current_day, -1, 0, "")

    def test_bad_record_is_preserved_not_silently_reset(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("broken-record", encoding="utf-8")
        journal = DailyJournal(self.path)
        self.assertTrue(journal.read_only)
        with self.assertRaises(OSError):
            journal.save()
        self.assertEqual(self.path.read_text(encoding="utf-8"), "broken-record")

    def test_invalid_nested_data_is_preserved(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"schema_version": 1, "days": {"2028-02-28": {"focus_seconds": "bad"}},
                "question_status": {}}
        self.path.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(DailyJournal(self.path).read_only)


if __name__ == "__main__":
    unittest.main()
