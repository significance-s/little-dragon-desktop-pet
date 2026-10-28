from __future__ import annotations

import calendar
from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk

from .journal import DailyJournal
from .study import format_duration


BG = "#f6f2fb"
CARD = "#ffffff"
PURPLE = "#74549d"
INK = "#42334f"
MUTED = "#8b7b9b"
FONT = ("Microsoft YaHei UI", 9)


def shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    index = (year - 1) * 12 + month - 1 + offset
    index = min(max(index, 0), 9999 * 12 - 1)
    year, month = divmod(index, 12)
    return year + 1, month + 1


class CalendarPanel:
    """Compact month calendar and local daily review; no background popups."""

    def __init__(self, root: tk.Tk, journal: DailyJournal, *, always_on_top: bool = False) -> None:
        self.journal = journal
        self.selected = journal.today()
        self.year, self.month = self.selected.year, self.selected.month
        self.window = tk.Toplevel(root)
        self.window.title("小龙娘 · 学习日历")
        self.window.configure(background=BG)
        self.window.attributes("-topmost", always_on_top)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(3, weight=1)
        self.dirty = False
        self.loading = False
        self.refresh_job: str | None = None
        self.month_var = tk.StringVar(master=root)
        self.date_var = tk.StringVar(master=root)
        self.stats_var = tk.StringVar(master=root)
        self.blockers_var = tk.StringVar(master=root)
        self.feedback_var = tk.StringVar(master=root)
        self.done_var = tk.StringVar(master=root)
        self.stuck_var = tk.StringVar(master=root)

        header = tk.Frame(self.window, background=BG)
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        header.columnconfigure(1, weight=1)
        self.previous_button = self._button(header, "‹", lambda: self.change_month(-1))
        self.previous_button.grid(row=0, column=0)
        tk.Label(header, textvariable=self.month_var, font=("Microsoft YaHei UI", 15, "bold"),
                 background=BG, foreground=INK).grid(row=0, column=1)
        self.next_button = self._button(header, "›", lambda: self.change_month(1))
        self.next_button.grid(row=0, column=2, padx=(0, 6))
        self.today_button = self._button(header, "今天", self.go_today)
        self.today_button.grid(row=0, column=3)

        self.grid_frame = tk.Frame(self.window, background=CARD, padx=8, pady=8)
        self.grid_frame.grid(row=1, column=0, sticky="ew", padx=18)
        for column, name in enumerate(("一", "二", "三", "四", "五", "六", "日")):
            self.grid_frame.columnconfigure(column, weight=1, uniform="weekday")
            tk.Label(self.grid_frame, text=name, background=CARD, foreground=MUTED, font=FONT
                     ).grid(row=0, column=column, sticky="ew", pady=(0, 4))
        self.day_buttons = []
        for index in range(42):
            button = tk.Button(
                self.grid_frame, font=FONT, borderwidth=0, relief="flat",
                background=CARD, foreground=INK, activebackground="#e9dff5",
                height=2, cursor="hand2", takefocus=True,
            )
            button.grid(row=index // 7 + 1, column=index % 7, sticky="ew", padx=2, pady=1)
            self.day_buttons.append(button)

        summary = tk.Frame(self.window, background=BG)
        summary.grid(row=2, column=0, sticky="ew", padx=18, pady=(12, 4))
        self.date_label = tk.Label(summary, textvariable=self.date_var,
                                  font=("Microsoft YaHei UI", 11, "bold"), foreground=INK,
                                  background=BG, anchor="w")
        self.date_label.pack(fill="x")
        tk.Label(summary, textvariable=self.stats_var, font=FONT, background=BG,
                 foreground=PURPLE, anchor="w", justify="left").pack(fill="x", pady=5)
        self.blockers_label = tk.Label(summary, textvariable=self.blockers_var, font=FONT,
                                      background=BG, foreground=MUTED, anchor="w", justify="left",
                                      wraplength=440)
        self.blockers_label.pack(fill="x")

        editor = tk.Frame(self.window, background=BG)
        editor.grid(row=3, column=0, sticky="nsew", padx=18, pady=(4, 0))
        editor.columnconfigure(0, weight=1)
        editor.rowconfigure(2, weight=1)
        manual = tk.Frame(editor, background=BG)
        manual.grid(row=0, column=0, sticky="w", pady=(0, 8))
        tk.Label(manual, text="额外补记：完成", font=FONT, background=BG, foreground=INK).pack(side="left")
        self.done_entry = ttk.Entry(manual, textvariable=self.done_var, width=5)
        self.done_entry.pack(side="left", padx=5)
        tk.Label(manual, text="不会", font=FONT, background=BG, foreground=INK).pack(side="left")
        self.stuck_entry = ttk.Entry(manual, textvariable=self.stuck_var, width=5)
        self.stuck_entry.pack(side="left", padx=5)
        tk.Label(manual, text="（不含答题卡）", font=FONT, background=BG, foreground=MUTED).pack(side="left")
        tk.Label(editor, text="今日复盘 / 下一步计划", font=FONT, background=BG,
                 foreground=INK, anchor="w").grid(row=1, column=0, sticky="w", pady=(0, 4))
        self.note_text = tk.Text(editor, height=4, width=1, font=FONT, wrap="word",
                                 relief="flat", background=CARD, foreground=INK, padx=10, pady=8,
                                 undo=True, highlightthickness=1, highlightbackground="#dfd3ec")
        self.note_text.grid(row=2, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(editor, orient="vertical", command=self.note_text.yview)
        scroll.grid(row=2, column=1, sticky="ns")
        self.note_text.configure(yscrollcommand=scroll.set)
        self.note_text.bind("<<Modified>>", self._note_changed)
        for var in (self.done_var, self.stuck_var):
            var.trace_add("write", self._mark_dirty)

        footer = tk.Frame(self.window, background=BG)
        footer.grid(row=4, column=0, sticky="ew", padx=18, pady=(10, 14))
        footer.columnconfigure(0, weight=1)
        controls = tk.Frame(footer, background=BG)
        controls.grid(row=0, column=0, sticky="w")
        self.save_button = self._button(controls, "保存复盘", self.save)
        self.save_button.pack(side="left")
        self.copy_button = self._button(controls, "复制当日小结", self.copy_summary)
        self.copy_button.pack(side="left", padx=8)
        recovery = tk.Frame(footer, background=BG)
        recovery.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.copy_draft_button = self._button(recovery, "复制未保存草稿", self.copy_draft)
        self.copy_draft_button.pack(side="left")
        self.discard_button = self._button(recovery, "放弃更改…", self.discard_draft)
        self.discard_button.pack(side="left", padx=8)
        self.feedback_label = tk.Label(footer, textvariable=self.feedback_var, font=FONT,
                                       background=BG, foreground=MUTED, anchor="w",
                                       wraplength=440, justify="left")
        self.feedback_label.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.window.bind("<Control-s>", lambda _event: self.save())
        self.window.bind("<Configure>", self._resize)
        self._load_selected()
        self.window.update_idletasks()
        width = max(480, self.window.winfo_reqwidth())
        height = max(640, self.window.winfo_reqheight())
        self.window.minsize(width, height)
        self.window.geometry(f"{width}x{height}")
        self._schedule_refresh()

    @staticmethod
    def _button(parent, text, command):
        return tk.Button(parent, text=text, command=command, font=FONT, borderwidth=0,
                         background="#e9dff5", foreground=PURPLE, activebackground="#d9c8ed",
                         padx=10, pady=6, cursor="hand2")

    def _resize(self, event) -> None:
        if event.widget is self.window:
            self.blockers_label.configure(wraplength=max(200, event.width - 42))
            self.feedback_label.configure(wraplength=max(200, event.width - 42))

    def _mark_dirty(self, *_args) -> None:
        if not self.loading and not self.journal.read_only:
            self.dirty = True
            self._update_draft_controls()
            self.feedback_var.set("尚未保存 · 切换日期或关闭窗口时自动保存")

    def _update_draft_controls(self) -> None:
        state = "normal" if self.dirty else "disabled"
        self.copy_draft_button.configure(state=state)
        self.discard_button.configure(state=state)

    def _note_changed(self, _event=None) -> None:
        if self.note_text.edit_modified():
            self._mark_dirty()
        self.note_text.edit_modified(False)

    def render_month(self) -> None:
        self.month_var.set(f"{self.year} 年 {self.month:02d} 月")
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(self.year, self.month)
        cells = [number for week in weeks for number in week]
        cells += [0] * (42 - len(cells))
        today = self.journal.today()
        for button, number in zip(self.day_buttons, cells):
            if not number:
                button.configure(text="", state="disabled", background=CARD, command=lambda: None)
                continue
            day = date(self.year, self.month, number)
            marker = "·" if self.journal.has_activity(day) else ""
            is_today = day == today
            text = f"{number}{' 今' if is_today else ''}\n{marker}"
            selected = day == self.selected
            button.configure(text=text, state="normal", command=lambda value=day: self.select_day(value),
                             background=PURPLE if selected else ("#f0e8f8" if is_today else CARD),
                             foreground="white" if selected else INK)

    def refresh_stats(self) -> None:
        item = self.journal.summary(self.selected)
        self.date_var.set(f"{self.selected:%Y.%m.%d}  ·  {'今天' if self.selected == self.journal.today() else '当日小结'}")
        self.stats_var.set(
            f"专注 {format_duration(item['focus_seconds'])}   ·   完成监督 {item['sessions']} 轮\n"
            f"完成 {item['done']} 题   不会 {item['stuck']}   存疑 {item['unsure']}   跳过 {item['skipped']}"
        )
        titles = "、".join(question["title"] for question in item["blockers"][:3])
        self.blockers_var.set(f"待复盘：{titles[:100]}" if titles else "还没有卡点记录。日历中 · 表示这天有学习或复盘记录。")

    def _load_selected(self) -> None:
        self.loading = True
        self.note_text.configure(state="normal")
        item = self.journal.summary(self.selected)
        self.done_var.set(str(item["manual_done"]))
        self.stuck_var.set(str(item["manual_stuck"]))
        self.note_text.delete("1.0", "end")
        self.note_text.insert("1.0", item["note"])
        self.note_text.edit_modified(False)
        self.loading = False
        self.dirty = False
        self._update_draft_controls()
        state = "disabled" if self.journal.read_only else "normal"
        for widget in (self.note_text, self.done_entry, self.stuck_entry, self.save_button):
            widget.configure(state=state)
        self.feedback_var.set(
            (self.journal.error or "学习记录暂不可写") + " · 编辑已停用，原文件未覆盖；修复后请重启。"
            if self.journal.read_only else "仅保存在本机；不会自动上传或发送到对话。"
        )
        self.refresh_stats()
        self.render_month()

    def save(self) -> bool:
        try:
            done, stuck = int(self.done_var.get()), int(self.stuck_var.get())
            self.journal.set_manual(self.selected, done, stuck, self.note_text.get("1.0", "end-1c"))
        except (ValueError, OSError) as exc:
            self.feedback_var.set(f"未保存：{exc} · 草稿仍在，可重试、复制或放弃更改。")
            return False
        self.dirty = False
        self._update_draft_controls()
        self.feedback_var.set("已保存在本机")
        self.refresh_stats()
        self.render_month()
        return True

    def select_day(self, day: date) -> None:
        if self.dirty and not self.save():
            return
        self.selected = day
        self.year, self.month = day.year, day.month
        self._load_selected()

    def change_month(self, offset: int) -> None:
        if self.dirty and not self.save():
            return
        self.year, self.month = shift_month(self.year, self.month, offset)
        self.render_month()

    def go_today(self) -> None:
        self.select_day(self.journal.today())

    def copy_summary(self) -> None:
        if self.dirty and not self.save():
            self.copy_draft()
            return
        self.window.clipboard_clear()
        self.window.clipboard_append(self.journal.markdown(self.selected))
        self.feedback_var.set("当日小结已复制，可手动粘贴到对话")

    def copy_draft(self) -> bool:
        draft = (
            f"学习记录未保存草稿 · {self.selected.isoformat()}\n"
            f"额外补记完成（输入值）：{self.done_var.get()}\n"
            f"额外补记不会（输入值）：{self.stuck_var.get()}\n\n"
            f"复盘 / 计划：\n{self.note_text.get('1.0', 'end-1c')}"
        )
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(draft)
            self.window.update_idletasks()
        except tk.TclError:
            self.feedback_var.set("草稿复制失败，内容仍保留在窗口中。")
            return False
        self.feedback_var.set("未保存草稿已复制；尚未写入学习记录。")
        return True

    def discard_draft(self) -> None:
        if self.dirty and messagebox.askyesno(
            "放弃未保存更改", "放弃当前复盘和补记的未保存更改？已保存记录不会删除。",
            parent=self.window,
        ):
            self._load_selected()

    def prepare_to_close(self) -> bool:
        if not self.dirty or self.save():
            return True
        choice = messagebox.askyesnocancel(
            "更改尚未保存",
            "当前复盘或补记未能保存。\n\n"
            "是：复制草稿后关闭。\n否：放弃未保存更改后关闭。\n取消：保留窗口，继续修改或重试。",
            parent=self.window, default=messagebox.CANCEL, icon=messagebox.WARNING,
        )
        if choice is None or (choice and not self.copy_draft()):
            return False
        self._load_selected()
        return True

    def hide(self) -> bool:
        if not self.prepare_to_close():
            return False
        self.window.withdraw()
        return True

    def show(self) -> None:
        self.refresh_stats()
        self.render_month()
        self.window.deiconify()
        self.window.lift()

    def _schedule_refresh(self) -> None:
        self.refresh_stats()
        self.render_month()
        self.refresh_job = self.window.after(30_000, self._schedule_refresh)

    def destroy(self) -> None:
        if self.refresh_job:
            self.window.after_cancel(self.refresh_job)
        self.window.destroy()
