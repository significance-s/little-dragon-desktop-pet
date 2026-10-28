import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from pet.question_bank import QuestionBankBridge, push_question_bank  # noqa: E402


SAMPLE_BANK = {
    "schema_version": 1,
    "set_id": "unit-test-set",
    "title": "单元测试题单",
    "source": "codex",
    "questions": [
        {"id": "q1", "title": "第一题", "prompt": "证明结论 A。"},
        {"id": "q2", "title": "第二题", "prompt": "计算结果 B。"},
    ],
}

RUNTIME_DATA = APP_DIR / "tests" / "runtime_data"


def sample_bank() -> dict:
    payload = dict(SAMPLE_BANK)
    payload["set_id"] = f"unit-test-{uuid4().hex}"
    payload["questions"] = [dict(question) for question in SAMPLE_BANK["questions"]]
    return payload


class QuestionBankTests(unittest.TestCase):
    def setUp(self) -> None:
        self._clean_runtime_files()

    def tearDown(self) -> None:
        self._clean_runtime_files()

    @staticmethod
    def _clean_runtime_files() -> None:
        for folder in (RUNTIME_DATA / "round_trip", RUNTIME_DATA / "reload"):
            for filename in (
                "question_inbox.json",
                "question_inbox.json.tmp",
                "question_state.json",
                "question_state.json.tmp",
                "question_outbox.json",
                "question_outbox.json.tmp",
            ):
                (folder / filename).unlink(missing_ok=True)
            returns = folder / "returns"
            if returns.is_dir():
                for result in returns.glob("*.json"):
                    result.unlink()

    def test_round_trip_and_result_export(self) -> None:
        data_dir = RUNTIME_DATA / "round_trip"
        push_question_bank(data_dir, sample_bank())
        bridge = QuestionBankBridge(data_dir)
        bank = bridge.load_if_changed()
        self.assertIsNotNone(bank)
        assert bank is not None
        self.assertEqual(bank.confirmed_count, 0)

        bank.questions[0].status = "done"
        bank.questions[1].status = "stuck"
        bank.questions[1].note = "不会构造判定函数"
        bridge.save_state()
        self.assertTrue(bank.all_confirmed)

        output = bridge.export_result()
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["summary"]["done"], 1)
        self.assertEqual(payload["summary"]["stuck"], 1)
        self.assertIn("不会构造判定函数", bridge.markdown_summary())
        self.assertGreaterEqual(len(list((data_dir / "returns").glob("*.json"))), 1)

    def test_saved_progress_is_merged_after_reload(self) -> None:
        data_dir = RUNTIME_DATA / "reload"
        payload = sample_bank()
        push_question_bank(data_dir, payload)
        first = QuestionBankBridge(data_dir)
        bank = first.load_if_changed()
        assert bank is not None
        bank.questions[0].status = "unsure"
        bank.questions[0].note = "需要再看证明"
        first.save_state()

        second = QuestionBankBridge(data_dir)
        reloaded = second.load_if_changed()
        assert reloaded is not None
        self.assertEqual(reloaded.questions[0].status, "unsure")
        self.assertEqual(reloaded.questions[0].note, "需要再看证明")

    def test_duplicate_ids_are_rejected(self) -> None:
        invalid = sample_bank()
        invalid["questions"] = [
            {"id": "same", "title": "A"},
            {"id": "same", "title": "B"},
        ]
        with self.assertRaises(ValueError):
            push_question_bank(RUNTIME_DATA / "invalid", invalid)


if __name__ == "__main__":
    unittest.main()
