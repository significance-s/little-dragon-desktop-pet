import sys
from pathlib import Path
import unittest


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from pet.study import StudySession, format_duration  # noqa: E402


class StudySessionTests(unittest.TestCase):
    def test_countdown_completes(self) -> None:
        session = StudySession("完成十道题", 2)
        self.assertFalse(session.tick())
        self.assertTrue(session.tick())
        self.assertTrue(session.completed)
        self.assertFalse(session.active)

    def test_pause_stops_countdown(self) -> None:
        session = StudySession("整理错题", 60)
        session.toggle_pause()
        session.tick(10)
        self.assertEqual(session.remaining_seconds, 60)
        session.toggle_pause()
        session.tick(10)
        self.assertEqual(session.remaining_seconds, 50)

    def test_duration_format(self) -> None:
        self.assertEqual(format_duration(65), "01:05")
        self.assertEqual(format_duration(3_661), "01:01:01")

    def test_invalid_session_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            StudySession("   ", 60)
        with self.assertRaises(ValueError):
            StudySession("做题", 0)


if __name__ == "__main__":
    unittest.main()
