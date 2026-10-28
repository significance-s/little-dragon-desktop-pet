from pathlib import Path
import sys
import tkinter as tk
import tkinter.font as tkfont
import unittest


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from pet.question_bank import QuestionBank  # noqa: E402
from pet.question_panel import QuestionCardPanel  # noqa: E402


class QuestionPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.saved = []
        self.returned = []
        self.bank = QuestionBank.from_dict({
            "set_id": "ui-check",
            "title": "算法练习 · 本轮答题卡",
            "questions": [
                {"id": "q1", "title": "最大化中位数", "prompt": "题目正文\n" * 80},
                {"id": "q2", "title": "边界条件检查"},
            ],
        })
        self.panel = QuestionCardPanel(
            self.root, self.bank,
            lambda: self.saved.append(self.bank.to_dict()),
            lambda: self.returned.append(True),
        )

    def tearDown(self) -> None:
        self.root.destroy()

    def test_footer_is_visible_at_minimum_size_and_high_dpi(self) -> None:
        for scaling in (1.333, 2.0):
            with self.subTest(scaling=scaling):
                self.root.tk.call("tk", "scaling", scaling)
                # DPI设置应在控件构造前生效。
                self.panel.window.destroy()
                self.panel = QuestionCardPanel(self.root, self.bank, lambda: None, lambda: None)
                width, height = self.panel.window.minsize()
                self.panel.window.geometry(f"{width}x{height}+0+0")
                self.root.update()
                window = self.panel.window
                for widget in (
                    *self.panel.status_buttons.values(),
                    self.panel.note_text,
                    self.panel.save_button,
                    self.panel.return_button,
                ):
                    self.assertTrue(widget.winfo_ismapped())
                    right = widget.winfo_rootx() - window.winfo_rootx() + widget.winfo_width()
                    bottom = widget.winfo_rooty() - window.winfo_rooty() + widget.winfo_height()
                    self.assertLessEqual(right, window.winfo_width())
                    self.assertLessEqual(bottom, window.winfo_height())
                self.assertGreaterEqual(self.panel.status_buttons["done"].winfo_height(), 40)
                line_height = tkfont.Font(font=self.panel.prompt_text["font"]).metrics("linespace")
                self.assertGreaterEqual(self.panel.prompt_text.winfo_height(), 3 * line_height)

    def test_explicit_note_save_navigation_and_submit(self) -> None:
        self.panel.note_text.insert("1.0", "最后一档的人数算错了")
        self.panel.save_button.invoke()
        self.assertEqual(self.saved[-1]["questions"][0]["note"], "最后一档的人数算错了")
        self.assertIn("已保存", self.panel.save_feedback_var.get())
        self.panel.status_buttons["unsure"].invoke()
        self.panel.next_button.invoke()
        self.assertEqual(str(self.panel.return_button["state"]), "disabled")
        self.panel.status_buttons["done"].invoke()
        self.assertEqual(str(self.panel.return_button["state"]), "normal")
        self.panel.return_button.invoke()
        self.assertEqual(self.returned, [True])
        self.panel.previous_button.invoke()
        self.assertEqual(self.panel.note_text.get("1.0", "end-1c"), "最后一档的人数算错了")


if __name__ == "__main__":
    unittest.main()
