from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from .question_bank import QuestionBank, STATUS_LABELS


BG = "#f3f0fa"
CARD = "#ffffff"
INK = "#302943"
MUTED = "#726780"
PURPLE = "#7153a6"
SOFT_PURPLE = "#ece4f7"
BORDER = "#ded5e9"
FONT = ("Microsoft YaHei UI", 10)


class QuestionCardPanel:
    def __init__(
        self,
        root: tk.Tk,
        bank: QuestionBank,
        on_change: Callable[[], None],
        on_return: Callable[[], None],
    ) -> None:
        self.bank = bank
        self.on_change = on_change
        self.on_return = on_return
        self.index = 0
        self._rendering = False

        self.window = tk.Toplevel(root)
        self.window.title("小龙娘 · 答题卡")
        self.window.configure(background=BG)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        self.window.columnconfigure(0, weight=1)
        # 只有正文可伸缩，状态、备注和操作区始终保留所需空间。
        self.window.rowconfigure(1, weight=1)

        self.bank_title_var = tk.StringVar(master=root)
        self.progress_var = tk.StringVar(master=root)
        self.question_title_var = tk.StringVar(master=root)
        self.meta_var = tk.StringVar(master=root)
        self.status_var = tk.StringVar(master=root)
        self.save_feedback_var = tk.StringVar(master=root)
        self.return_hint_var = tk.StringVar(master=root)

        header = tk.Frame(self.window, background=BG)
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 12))
        header.columnconfigure(0, weight=1)
        tk.Label(
            header, text="小龙娘陪你做题 / CODEX",
            font=("Microsoft YaHei UI", 9), foreground=PURPLE, background=BG,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.bank_title_label = tk.Label(
            header, textvariable=self.bank_title_var,
            font=("Microsoft YaHei UI", 15, "bold"), foreground=INK,
            background=BG, anchor="w", justify="left",
        )
        self.bank_title_label.grid(row=1, column=0, sticky="ew", pady=(5, 8))
        tk.Label(
            header, textvariable=self.progress_var, font=FONT,
            foreground=MUTED, background=BG, anchor="w",
        ).grid(row=2, column=0, sticky="w")
        self.progress_bar = tk.Frame(header, height=6, background=SOFT_PURPLE)
        self.progress_bar.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.progress_fill = tk.Frame(self.progress_bar, background=PURPLE)
        self.progress_fill.place(x=0, y=0, relheight=1, relwidth=0)

        content = self._card(self.window)
        content.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 12))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)
        self.question_title_label = tk.Label(
            content, textvariable=self.question_title_var,
            font=("Microsoft YaHei UI", 12, "bold"), foreground=INK,
            background=CARD, anchor="w", justify="left",
        )
        self.question_title_label.grid(row=0, column=0, sticky="ew", padx=16, pady=(13, 4))
        self.meta_label = tk.Label(
            content, textvariable=self.meta_var, font=("Microsoft YaHei UI", 9),
            foreground=PURPLE, background=CARD, anchor="w", justify="left",
        )
        self.meta_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        self.prompt_text = self._text_area(content, row=2, height=4, readonly=True)

        self.footer = self._card(self.window)
        self.footer.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 18))
        self.footer.columnconfigure(0, weight=1)
        tk.Label(
            self.footer, text="这道题的状态", font=("Microsoft YaHei UI", 10, "bold"),
            foreground=INK, background=CARD, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(13, 8))

        self.status_row = tk.Frame(self.footer, background=CARD)
        self.status_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        self.status_buttons: dict[str, tk.Radiobutton] = {}
        for column, (status, label) in enumerate(STATUS_LABELS.items()):
            self.status_row.columnconfigure(column, weight=1, uniform="status")
            button = tk.Radiobutton(
                self.status_row, text=label, variable=self.status_var, value=status,
                command=self._save_current, indicatoron=False,
                font=("Microsoft YaHei UI", 11, "bold"),
                background=BG, foreground=INK, selectcolor=SOFT_PURPLE,
                activebackground=SOFT_PURPLE, activeforeground=PURPLE,
                relief="flat", offrelief="flat", borderwidth=0,
                padx=10, pady=10, cursor="hand2", highlightthickness=1,
                highlightbackground=BORDER,
            )
            button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
            self.status_buttons[status] = button

        note_header = tk.Frame(self.footer, background=CARD)
        note_header.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))
        tk.Label(
            note_header, text="备注 · 卡点、错因、想问的问题",
            font=FONT, foreground=INK, background=CARD,
        ).pack(side="left")
        self.save_button = self._button(note_header, "保存备注", self._save_current)
        self.save_button.pack(side="right")
        self.note_text = self._text_area(self.footer, row=3, height=3)
        self.note_text.bind("<FocusOut>", lambda _event: self._save_current())
        self.note_text.bind("<<Modified>>", self._note_modified)
        self.note_text.bind("<Control-Return>", self._save_shortcut)

        tk.Label(
            self.footer, textvariable=self.save_feedback_var,
            font=("Microsoft YaHei UI", 9), foreground=PURPLE,
            background=CARD, anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 10))

        controls = tk.Frame(self.footer, background=CARD)
        controls.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 6))
        controls.columnconfigure(2, weight=1)
        self.previous_button = self._button(controls, "← 上一题", self._previous)
        self.previous_button.grid(row=0, column=0, sticky="w")
        self.next_button = self._button(controls, "下一题 →", self._next)
        self.next_button.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.return_button = self._button(
            controls, "提交题单并生成回执", self._return_to_codex, primary=True,
        )
        self.return_button.grid(row=0, column=3, sticky="e", padx=(12, 0))
        tk.Label(
            self.footer, textvariable=self.return_hint_var,
            font=("Microsoft YaHei UI", 9), foreground=MUTED,
            background=CARD, anchor="w",
        ).grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 13))

        self.window.bind("<Configure>", self._resize_labels)
        self._render()
        self.window.update_idletasks()
        # 用实际字体/DPI测量底部尺寸，给正文预留可滚动的空间。
        min_width = max(620, self.footer.winfo_reqwidth() + 44)
        min_height = (
            header.winfo_reqheight() + self.footer.winfo_reqheight()
            + content.winfo_reqheight() + 60
        )
        self.window.minsize(min_width, min_height)
        self.window.geometry(f"{max(760, min_width)}x{max(720, min_height)}")

    @staticmethod
    def _card(parent: tk.Misc) -> tk.Frame:
        return tk.Frame(
            parent, background=CARD, highlightbackground=BORDER, highlightthickness=1,
        )

    @staticmethod
    def _button(
        parent: tk.Misc, text: str, command: Callable[[], None], primary: bool = False,
    ) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, font=FONT,
            background=PURPLE if primary else SOFT_PURPLE,
            foreground="white" if primary else PURPLE,
            activebackground="#60428f" if primary else "#ded0ee",
            activeforeground="white" if primary else PURPLE,
            disabledforeground="#9b91ac", relief="flat", borderwidth=0,
            padx=14, pady=8, cursor="hand2",
        )

    @staticmethod
    def _text_area(parent: tk.Frame, row: int, height: int, readonly: bool = False) -> tk.Text:
        wrapper = tk.Frame(parent, background=CARD)
        wrapper.grid(row=row, column=0, sticky="nsew", padx=16, pady=(0, 8))
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)
        text = tk.Text(
            wrapper, height=height, width=1, wrap="word", font=FONT,
            background=CARD if readonly else "#faf8fd", foreground=INK,
            insertbackground=PURPLE, selectbackground=SOFT_PURPLE,
            relief="flat", borderwidth=0, padx=10, pady=8,
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=PURPLE, undo=not readonly,
        )
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        if readonly:
            text.configure(state="disabled")
        return text

    def _resize_labels(self, event: tk.Event) -> None:
        if event.widget is self.window:
            wraplength = max(200, event.width - 80)
            for label in (self.bank_title_label, self.question_title_label, self.meta_label):
                label.configure(wraplength=wraplength)

    def set_bank(self, bank: QuestionBank) -> None:
        self.bank = bank
        self.index = 0
        self._render()

    def show(self) -> None:
        self._save_current()
        self.window.deiconify()
        self.window.lift()

    def hide(self) -> None:
        self._save_current()
        self.window.withdraw()

    def _note_modified(self, _event: tk.Event) -> None:
        note_changed = (
            self.note_text.get("1.0", "end-1c")
            != self.bank.questions[self.index].note
        )
        if self.note_text.edit_modified() and not self._rendering and note_changed:
            self.save_feedback_var.set("备注待保存 · 点击保存备注，或按 Ctrl + Enter")
        self.note_text.edit_modified(False)

    def _save_shortcut(self, _event: tk.Event) -> str:
        self._save_current()
        return "break"

    def _save_current(self) -> None:
        question = self.bank.questions[self.index]
        question.status = self.status_var.get()
        question.note = self.note_text.get("1.0", "end-1c")
        self.note_text.edit_modified(False)
        try:
            self.on_change()
        except OSError:
            self.save_feedback_var.set("保存失败，请检查文件权限后再次点击保存备注。")
        else:
            self.save_feedback_var.set("状态与备注已保存 · 提交题单后一起返回 Codex")
        self._update_progress()

    def _render(self) -> None:
        self._rendering = True
        question = self.bank.questions[self.index]
        self.bank_title_var.set(self.bank.title)
        self.question_title_var.set(f"{self.index + 1:02d}  {question.title}")
        metadata = [item for item in (question.difficulty, " · ".join(question.tags)) if item]
        self.meta_var.set(" / ".join(metadata) or "按自己的节奏完成，遇到卡点记在下方。")
        self.status_var.set(question.status)
        self.prompt_text.configure(state="normal")
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", question.prompt or "（题目正文未附带，请按标题或来源完成）")
        self.prompt_text.configure(state="disabled")
        self.note_text.delete("1.0", "end")
        self.note_text.insert("1.0", question.note)
        self.note_text.edit_modified(False)
        self._rendering = False
        self.save_feedback_var.set("选择状态自动保存 · 备注也可用 Ctrl + Enter 保存")
        self.previous_button.configure(state="normal" if self.index > 0 else "disabled")
        self.next_button.configure(
            state="normal" if self.index + 1 < len(self.bank.questions) else "disabled",
        )
        self._update_progress()

    def _update_progress(self) -> None:
        total = len(self.bank.questions)
        confirmed = self.bank.confirmed_count
        self.progress_var.set(f"第 {self.index + 1} / {total} 题    ·    已确认 {confirmed} / {total}")
        self.progress_fill.place(relwidth=confirmed / total)
        for status, button in self.status_buttons.items():
            selected = status == self.status_var.get()
            button.configure(
                foreground=PURPLE if selected else MUTED,
                highlightbackground=PURPLE if selected else BORDER,
            )
        self.return_button.configure(state="normal" if self.bank.all_confirmed else "disabled")
        self.return_hint_var.set(
            "全部确认完成，可以提交；备注会包含在回执中。"
            if self.bank.all_confirmed else f"还需确认 {total - confirmed} 题，之后可提交整份题单。"
        )

    def _previous(self) -> None:
        self._save_current()
        if self.index > 0:
            self.index -= 1
            self._render()

    def _next(self) -> None:
        self._save_current()
        if self.index + 1 < len(self.bank.questions):
            self.index += 1
            self._render()

    def _return_to_codex(self) -> None:
        self._save_current()
        if self.bank.all_confirmed:
            self.on_return()
