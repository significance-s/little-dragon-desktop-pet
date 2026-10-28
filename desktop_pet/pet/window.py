from __future__ import annotations

import json
import random
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, simpledialog
from typing import TYPE_CHECKING

from PIL import Image, ImageSequence, ImageTk

from .assets import AssetCatalog, STATE_LABELS
from .countdown import CountdownPanel, EventCountdown
from .question_bank import QuestionBankBridge
from .question_panel import QuestionCardPanel
from .study import StudySession, format_duration
from .journal import DailyJournal
from .calendar_panel import CalendarPanel
from .preferences import clean_retired_countdown

if TYPE_CHECKING:
    from .tray import TrayController


@dataclass
class LoadedAnimation:
    frames: list[ImageTk.PhotoImage]
    durations: list[int]


STATE_TIMEOUTS_MS: dict[str, int] = {
    "wave": 2_200,
    "work": 6_000,
    "eat": 4_500,
    "sleep": 9_000,
    "victory": 2_300,
    "pet": 2_000,
}

MIN_SIZE = 128
MAX_SIZE = 2048
SIZE_STEP = 20
SIZE_PRESETS = (160, 220, 260, 320, 384, 512, 768, 1024, 1536, 2048)
LARGE_ANIMATION_SIZE = 768
ALPHA_CUTOFF = 48
STUDY_PANEL_WIDTH = 320
STUDY_PANEL_HEIGHT = 215
STUDY_PANEL_GAP = 10
STUDY_PANEL_BG = "#f7f2ff"
STUDY_PANEL_BORDER = "#8d78b8"
STUDY_MESSAGES = (
    "本龙盯着呢，先把眼前这一步写完。",
    "别急着看答案，先把已知条件列清楚。",
    "卡住就标记一下，换一道再回来。",
    "保持节奏，做完记得检查单位和符号。",
    "已经坚持一阵子了，再稳稳推进一点。",
)


def clamp_size(value: int) -> int:
    return max(MIN_SIZE, min(int(value), MAX_SIZE))


def prepare_frame_for_window(
    frame: Image.Image,
    size: int,
    transparent_color: str,
    color_key_enabled: bool,
) -> Image.Image:
    rgba = (
        frame.convert("RGBA")
        .convert("RGBa")
        .resize((size, size), Image.Resampling.LANCZOS)
        .convert("RGBA")
    )
    if not color_key_enabled:
        return rgba

    # Windows 的 transparentcolor 是色键透明。先把每帧铺满色键背景，
    # 可确保位移/缩放后旧像素被真正擦除，避免透明帧留下矩形色块。
    alpha = rgba.getchannel("A").point(
        lambda value: 255 if value >= ALPHA_CUTOFF else 0
    )
    keyed = Image.new("RGB", rgba.size, transparent_color)
    keyed.paste(rgba.convert("RGB"), mask=alpha)
    return keyed


def study_panel_position(
    pet_x: int,
    pet_y: int,
    pet_size: int,
    screen_width: int,
    screen_height: int,
) -> tuple[int, int]:
    """优先停靠在桌宠右侧，空间不足时自动换到左侧或屏幕内侧。"""
    right_x = pet_x + pet_size + STUDY_PANEL_GAP
    left_x = pet_x - STUDY_PANEL_WIDTH - STUDY_PANEL_GAP
    if right_x + STUDY_PANEL_WIDTH <= screen_width:
        panel_x = right_x
    elif left_x >= 0:
        panel_x = left_x
    else:
        panel_x = min(
            max(0, pet_x + pet_size - STUDY_PANEL_WIDTH),
            max(0, screen_width - STUDY_PANEL_WIDTH),
        )

    centered_y = pet_y + (pet_size - STUDY_PANEL_HEIGHT) // 2
    panel_y = min(
        max(0, centered_y),
        max(0, screen_height - STUDY_PANEL_HEIGHT),
    )
    return panel_x, panel_y


class PetWindow:
    def __init__(
        self,
        root: tk.Tk,
        assets: AssetCatalog,
        config: dict,
        config_path: Path | None = None,
    ) -> None:
        self.root = root
        self.assets = assets
        config = clean_retired_countdown(config)
        self.config = dict(config)
        self.config_path = config_path
        self.size = clamp_size(config.get("size", 260))
        self.opacity = float(config.get("opacity", 1.0))
        self.always_on_top = bool(config.get("always_on_top", True))
        self.random_actions = bool(config.get("random_actions", True))
        self.random_min_ms = int(config.get("random_action_min_seconds", 18) * 1000)
        self.random_max_ms = int(config.get("random_action_max_seconds", 35) * 1000)
        self.transparent_color = str(config.get("transparent_color", "#010203"))

        self.state = "idle"
        self.frame_index = 0
        self.animation_job: str | None = None
        self.return_job: str | None = None
        self.random_job: str | None = None
        self.drag_origin: tuple[int, int, int, int] | None = None
        self.dragged = False
        self.cache: dict[str, LoadedAnimation] = {}
        self.study_session: StudySession | None = None
        self.study_job: str | None = None
        self.study_panel: tk.Toplevel | None = None
        self.study_drag_origin: tuple[int, int, int, int] | None = None
        self.study_goal_var = tk.StringVar(master=root)
        self.study_time_var = tk.StringVar(master=root)
        self.study_message_var = tk.StringVar(master=root)
        self.study_pause_button: tk.Button | None = None
        self.tray: TrayController | None = None
        self.hidden_to_tray = False
        event_config = config.get("event_countdown")
        self.event_configured = (
            isinstance(event_config, dict) and bool(event_config.get("title") and event_config.get("date"))
        )
        try:
            self.event_countdown = EventCountdown.from_config(config.get("event_countdown"))
        except ValueError:
            # 手工改错日期不应使整个桌宠无法启动；打开设置即可修正。
            self.event_countdown = EventCountdown.from_config(None)
            self.event_configured = False
        self.countdown_enabled = tk.BooleanVar(
            master=root,
            value=self.event_configured and bool(event_config.get("enabled", False)),
        )
        self.countdown_panel: CountdownPanel | None = None
        self.countdown_job: str | None = None
        data_dir = (config_path.parent if config_path is not None else Path.cwd()) / "data"
        self.question_bridge = QuestionBankBridge(data_dir)
        self.journal = DailyJournal(data_dir / "daily_journal.json")
        self.calendar_panel: CalendarPanel | None = None
        self.study_recorded = False
        self.question_panel: QuestionCardPanel | None = None
        self.question_poll_job: str | None = None
        self.question_poll_ms = max(
            500,
            int(float(config.get("question_sync_interval_seconds", 2)) * 1000),
        )

        self._configure_window(config)
        self.label = tk.Label(
            root,
            borderwidth=0,
            highlightthickness=0,
            background=self.transparent_color,
            cursor="hand2",
        )
        self.label.pack(fill="both", expand=True)
        self._bind_events()
        self.size_var = tk.IntVar(value=self.size)
        self.menu = self._build_menu()
        self.set_state("idle", return_to_idle=False)
        self._schedule_random_action()
        self._poll_question_bank(initial=True)
        self._refresh_event_countdown()

    def _configure_window(self, config: dict) -> None:
        self.root.title("小龙娘桌宠")
        self.root.overrideredirect(True)
        self.root.configure(background=self.transparent_color)
        self.root.attributes("-topmost", self.always_on_top)
        self.root.attributes("-alpha", max(0.2, min(self.opacity, 1.0)))
        self.color_key_enabled = False
        try:
            self.root.wm_attributes("-transparentcolor", self.transparent_color)
            self.color_key_enabled = True
        except tk.TclError:
            pass

        self.root.update_idletasks()
        x = config.get("x")
        y = config.get("y")
        if x is None:
            x = self.root.winfo_screenwidth() - self.size - 32
        if y is None:
            y = self.root.winfo_screenheight() - self.size - 72
        self.root.geometry(f"{self.size}x{self.size}{int(x):+d}{int(y):+d}")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _bind_events(self) -> None:
        self.label.bind("<ButtonPress-1>", self._on_press)
        self.label.bind("<B1-Motion>", self._on_drag)
        self.label.bind("<ButtonRelease-1>", self._on_release)
        self.label.bind("<Double-Button-1>", lambda _event: self.set_state("wave"))
        self.label.bind("<Button-3>", self._show_menu)
        self.root.bind("<Control-MouseWheel>", self._on_size_wheel)
        self.root.bind("<Escape>", lambda _event: self.hide_to_tray())

    def _build_menu(self) -> tk.Menu:
        def submenu(parent) -> tk.Menu:
            return tk.Menu(
                parent, tearoff=False, font=("Microsoft YaHei UI", 10),
                background="#faf7ff", foreground="#493957",
                activebackground="#e7dcf4", activeforeground="#593b80",
                disabledforeground="#a99ab8", selectcolor="#74549d",
                borderwidth=1, activeborderwidth=0,
            )

        menu = submenu(self.root)
        menu.configure(postcommand=self._refresh_menu_state)
        menu.add_command(label="小龙娘 · 桌面助手", state="disabled")
        menu.add_separator()
        menu.add_command(label="开始专注…", command=self.start_study_session)
        menu.add_command(label="学习日历与小结", command=self.open_calendar)
        menu.add_command(label="答题卡", command=self.open_question_cards)
        self.focus_menu = submenu(menu)
        self.focus_menu.add_command(label="暂停专注", command=self._toggle_study_pause)
        self.focus_menu.add_command(label="显示专注面板", command=self._show_study_panel)
        self.focus_menu.add_separator()
        self.focus_menu.add_command(label="完成本轮", command=lambda: self._finish_study(True))
        self.focus_menu.add_command(label="结束本轮", command=self._stop_study)
        menu.add_cascade(label="专注控制", menu=self.focus_menu)
        menu.add_separator()
        self.action_menu = submenu(menu)
        for state in ("idle", "wave", "work", "eat", "sleep", "victory", "pet"):
            self.action_menu.add_command(
                label=STATE_LABELS[state],
                command=lambda selected=state: self.set_state(selected),
            )
        menu.add_cascade(label="互动动作", menu=self.action_menu)
        self.countdown_menu = submenu(menu)
        self.countdown_menu.add_checkbutton(
            label="显示提醒", variable=self.countdown_enabled,
            command=self._toggle_event_countdown,
        )
        self.countdown_menu.add_command(label="设置名称与日期…", command=self._edit_event_countdown)
        self.countdown_menu.add_separator()
        self.countdown_menu.add_command(label="清除提醒…", command=self._clear_event_countdown)
        menu.add_cascade(label="日期倒计时", menu=self.countdown_menu)
        size_menu = submenu(menu)
        for pixels in SIZE_PRESETS:
            size_menu.add_radiobutton(
                label=f"{pixels} px",
                variable=self.size_var,
                value=pixels,
                command=lambda selected=pixels: self.set_size(selected),
            )
        size_menu.add_separator()
        size_menu.add_command(
            label=f"缩小 {SIZE_STEP} px",
            command=lambda: self.set_size(self.size - SIZE_STEP),
        )
        size_menu.add_command(
            label=f"放大 {SIZE_STEP} px",
            command=lambda: self.set_size(self.size + SIZE_STEP),
        )
        size_menu.add_separator()
        size_menu.add_command(label="手动输入…", command=self._ask_size)
        menu.add_cascade(label="调整大小", menu=size_menu, accelerator="Ctrl+滚轮")
        menu.add_separator()
        menu.add_command(label="隐藏到托盘", command=self.hide_to_tray, accelerator="Esc")
        menu.add_command(label="退出", command=self.close)
        self._refresh_menu_state()
        return menu

    def _refresh_menu_state(self) -> None:
        session = self.study_session
        active = session is not None and session.active
        self.focus_menu.entryconfigure(
            0, label="继续专注" if active and session.paused else "暂停专注",
            state="normal" if active else "disabled",
        )
        self.focus_menu.entryconfigure(1, state="normal" if session is not None else "disabled")
        for index in (3, 4):
            self.focus_menu.entryconfigure(index, state="normal" if active else "disabled")
        self.countdown_menu.entryconfigure(3, state="normal" if self.event_configured else "disabled")

    def attach_tray(self, tray: TrayController) -> None:
        self.tray = tray

    def show_pet(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", self.always_on_top)
        self.hidden_to_tray = False
        self._update_event_countdown_panel()

    def hide_to_tray(self) -> None:
        if self.countdown_panel is not None:
            self.countdown_panel.hide()
        if self.study_panel is not None and self.study_panel.winfo_exists():
            self.study_panel.withdraw()
        if self.question_panel is not None and self.question_panel.window.winfo_exists():
            self.question_panel.hide()
        if self.calendar_panel is not None and self.calendar_panel.window.winfo_exists():
            self.calendar_panel.hide()
        self.root.withdraw()
        self.hidden_to_tray = True

    def toggle_visibility(self) -> None:
        if self.hidden_to_tray:
            self.show_pet()
        else:
            self.hide_to_tray()

    def _update_event_countdown_panel(self) -> None:
        if not self.countdown_enabled.get() or self.hidden_to_tray:
            if self.countdown_panel is not None:
                self.countdown_panel.hide()
            return
        if self.countdown_panel is None:
            self.countdown_panel = CountdownPanel(
                self.root, self.event_countdown, always_on_top=self.always_on_top,
                on_edit=self._edit_event_countdown, on_hide=self._hide_event_countdown,
                on_press=self._on_study_press, on_drag=self._on_study_drag,
                on_release=self._on_study_release,
            )
        self.countdown_panel.event = self.event_countdown
        self.countdown_panel.update()
        self._position_event_countdown()
        self.countdown_panel.show()

    def _position_event_countdown(
        self, pet_x: int | None = None, pet_y: int | None = None,
    ) -> None:
        if self.countdown_panel is not None:
            self.root.update_idletasks()
            self.countdown_panel.position(
                self.root.winfo_x() if pet_x is None else pet_x,
                self.root.winfo_y() if pet_y is None else pet_y,
                self.size,
            )

    def _refresh_event_countdown(self) -> None:
        if self.countdown_job is not None:
            self.root.after_cancel(self.countdown_job)
        self.countdown_job = None
        self._update_event_countdown_panel()
        # 自动跨日刷新，也能在系统休眠后恢复时重新计算；不是递减缓存天数。
        self.countdown_job = self.root.after(30_000, self._refresh_event_countdown)

    def _toggle_event_countdown(self) -> None:
        if self.countdown_enabled.get() and not self.event_configured:
            self.countdown_enabled.set(False)
            self._edit_event_countdown()
            return
        self._update_event_countdown_panel()
        self._persist_config()

    def _hide_event_countdown(self) -> None:
        self.countdown_enabled.set(False)
        self._toggle_event_countdown()

    def show_event_countdown(self) -> None:
        if not self.event_configured:
            self._edit_event_countdown()
            return
        self.countdown_enabled.set(True)
        self.show_pet()
        self._persist_config()

    def open_calendar(self) -> None:
        if self.calendar_panel is None or not self.calendar_panel.window.winfo_exists():
            self.calendar_panel = CalendarPanel(
                self.root, self.journal, always_on_top=self.always_on_top,
            )
        else:
            self.calendar_panel.show()

    def _save_question_state(self) -> None:
        self.question_bridge.save_state()
        self.journal.record_bank(self.question_bridge.bank)
        if self.calendar_panel is not None and self.calendar_panel.window.winfo_exists():
            self.calendar_panel.refresh_stats()
            self.calendar_panel.render_month()

    def _edit_event_countdown(self) -> None:
        self.show_pet()
        title = simpledialog.askstring(
            "日期倒计时", "提醒名称（最多 80 个字符）：", parent=self.root,
            initialvalue=self.event_countdown.title,
        )
        if title is None:
            return
        target = simpledialog.askstring(
            "日期倒计时", "目标日期（YYYY-MM-DD，按上海日期计算）：", parent=self.root,
            initialvalue=self.event_countdown.target_date.isoformat(),
        )
        if target is None:
            return
        try:
            event = EventCountdown.parse(title, target)
        except ValueError as exc:
            messagebox.showerror("倒计时设置无效", str(exc), parent=self.root)
            return
        self.event_countdown = event
        self.event_configured = True
        self.countdown_enabled.set(True)
        self._update_event_countdown_panel()
        self._persist_config()

    def _clear_event_countdown(self) -> None:
        if not messagebox.askyesno(
            "清除日期提醒", "清除当前提醒的名称和日期？其他学习记录不会删除。", parent=self.root,
        ):
            return
        self.event_countdown = EventCountdown.from_config(None)
        self.event_configured = False
        self.countdown_enabled.set(False)
        if self.countdown_panel is not None:
            self.countdown_panel.window.destroy()
            self.countdown_panel = None
        self._persist_config()

    def open_question_cards(self) -> None:
        self.show_pet()
        bank = self.question_bridge.bank
        if bank is None:
            bank = self.question_bridge.load_if_changed()
            if bank is not None:
                try:
                    self.journal.prime_bank(bank)
                except OSError as exc:
                    self.journal.error = str(exc)
        if bank is None:
            if self.question_bridge.last_error:
                messagebox.showerror(
                    "题库同步失败",
                    self.question_bridge.last_error,
                    parent=self.root,
                )
            else:
                messagebox.showinfo(
                    "暂无 Codex 题单",
                    "还没有收到推荐题单。\n"
                    "在 Codex 中说“把推荐题单同步给桌宠”即可。",
                    parent=self.root,
                )
            return

        if self.question_panel is None or not self.question_panel.window.winfo_exists():
            self.question_panel = QuestionCardPanel(
                self.root,
                bank,
                on_change=self._save_question_state,
                on_return=self._return_question_results,
            )
        else:
            if self.question_panel.bank is not bank:
                self.question_panel.set_bank(bank)
            self.question_panel.show()

    def _poll_question_bank(self, initial: bool = False) -> None:
        self.question_poll_job = None
        bank = self.question_bridge.load_if_changed()
        if bank is not None:
            try:
                self.journal.prime_bank(bank)
            except OSError as exc:
                self.journal.error = str(exc)
            if self.question_panel is not None and self.question_panel.window.winfo_exists():
                self.question_panel.set_bank(bank)
            if not initial and self.tray is not None:
                self.tray.notify(
                    "收到 Codex 推荐题单",
                    f"{bank.title} · 共 {len(bank.questions)} 题",
                )
        self.question_poll_job = self.root.after(
            self.question_poll_ms,
            self._poll_question_bank,
        )

    def _return_question_results(self) -> None:
        try:
            output_path = self.question_bridge.export_result()
        except (OSError, ValueError) as exc:
            messagebox.showerror("返回失败", str(exc), parent=self.root)
            return

        summary = self.question_bridge.markdown_summary()
        self.root.clipboard_clear()
        self.root.clipboard_append(summary)
        self.root.update_idletasks()
        if self.tray is not None:
            self.tray.notify(
                "答题卡已返回",
                "结构化回执已保存，Markdown 摘要已复制。",
            )
        messagebox.showinfo(
            "已返回 Codex",
            f"回执已写入：\n{output_path}\n\n"
            "摘要已复制到剪贴板。回到 Codex 后直接粘贴，"
            "或让 Codex 读取桌宠答题卡结果即可。",
            parent=self.root,
        )

    def set_size(self, value: int) -> None:
        new_size = clamp_size(value)
        self.size_var.set(new_size)
        if new_size == self.size:
            return

        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.size = new_size
        self.cache.clear()
        self.root.geometry(f"{self.size}x{self.size}{x:+d}{y:+d}")
        self.set_state(self.state, return_to_idle=self.state != "idle")
        self._position_study_panel(x, y)
        self._position_event_countdown(x, y)
        self._persist_config()

    def _ask_size(self) -> None:
        selected = simpledialog.askinteger(
            "调整桌宠大小",
            f"请输入边长（{MIN_SIZE}～{MAX_SIZE} px）：",
            parent=self.root,
            initialvalue=self.size,
            minvalue=MIN_SIZE,
            maxvalue=MAX_SIZE,
        )
        if selected is not None:
            self.set_size(selected)

    def _on_size_wheel(self, event: tk.Event) -> str:
        delta = int(getattr(event, "delta", 0))
        if delta:
            steps = max(1, abs(delta) // 120)
            direction = 1 if delta > 0 else -1
            self.set_size(self.size + direction * steps * SIZE_STEP)
        return "break"

    def start_study_session(self) -> None:
        self.show_pet()
        if self.study_session is not None and self.study_session.active:
            self._show_study_panel()
            self.study_message_var.set("这一轮还没结束呢，先把它做完，哼。")
            return

        goal = simpledialog.askstring(
            "开始做题监督",
            "这轮准备完成什么？",
            parent=self.root,
            initialvalue="完成今天的练习题",
        )
        if goal is None or not goal.strip():
            return
        minutes = simpledialog.askinteger(
            "设置监督时长",
            "本轮做多少分钟？",
            parent=self.root,
            initialvalue=25,
            minvalue=1,
            maxvalue=480,
        )
        if minutes is None:
            return

        self.study_session = StudySession(goal, minutes * 60)
        self.study_recorded = False
        self._ensure_study_panel()
        self._update_study_panel()
        self.set_state("work", return_to_idle=False)
        self._schedule_study_tick()

    def _ensure_study_panel(self) -> None:
        if self.study_panel is not None and self.study_panel.winfo_exists():
            self.study_panel.deiconify()
            self.study_panel.lift()
            return

        panel = tk.Toplevel(self.root)
        panel.overrideredirect(True)
        panel.resizable(False, False)
        panel.attributes("-topmost", self.always_on_top)
        panel.configure(
            background=STUDY_PANEL_BG,
            highlightbackground=STUDY_PANEL_BORDER,
            highlightthickness=1,
        )
        self.study_panel = panel
        self._position_study_panel()

        title_row = tk.Frame(panel, background=STUDY_PANEL_BG)
        title_row.pack(fill="x", padx=10, pady=(7, 0))
        title_label = tk.Label(
            title_row,
            text="小龙娘 · 做题监督",
            font=("Microsoft YaHei UI", 9, "bold"),
            foreground="#5d477f",
            background=STUDY_PANEL_BG,
            cursor="fleur",
        )
        title_label.pack(side="left", fill="x", expand=True)
        tk.Button(
            title_row,
            text="×",
            borderwidth=0,
            background=STUDY_PANEL_BG,
            activebackground="#eadffc",
            foreground="#6c568e",
            command=panel.withdraw,
        ).pack(side="right")

        goal_label = tk.Label(
            panel,
            textvariable=self.study_goal_var,
            font=("Microsoft YaHei UI", 10, "bold"),
            wraplength=286,
            justify="left",
            anchor="w",
            background=STUDY_PANEL_BG,
            cursor="fleur",
        )
        goal_label.pack(fill="x", padx=16, pady=(8, 4))
        time_label = tk.Label(
            panel,
            textvariable=self.study_time_var,
            font=("Segoe UI", 28, "bold"),
            foreground="#403154",
            background=STUDY_PANEL_BG,
            cursor="fleur",
        )
        time_label.pack(pady=2)
        message_label = tk.Label(
            panel,
            textvariable=self.study_message_var,
            font=("Microsoft YaHei UI", 9),
            wraplength=286,
            justify="center",
            background=STUDY_PANEL_BG,
            cursor="fleur",
        )
        message_label.pack(fill="x", padx=16, pady=(2, 10))

        buttons = tk.Frame(panel, background=STUDY_PANEL_BG)
        buttons.pack(pady=(0, 12))
        self.study_pause_button = tk.Button(
            buttons,
            text="暂停",
            width=8,
            command=self._toggle_study_pause,
        )
        self.study_pause_button.pack(side="left", padx=4)
        tk.Button(
            buttons,
            text="我做完了",
            width=9,
            command=lambda: self._finish_study(True),
        ).pack(side="left", padx=4)
        tk.Button(
            buttons,
            text="结束",
            width=7,
            command=self._stop_study,
        ).pack(side="left", padx=4)

        for drag_widget in (title_row, title_label, goal_label, time_label, message_label):
            drag_widget.bind("<ButtonPress-1>", self._on_study_press)
            drag_widget.bind("<B1-Motion>", self._on_study_drag)
            drag_widget.bind("<ButtonRelease-1>", self._on_study_release)

    def _position_study_panel(
        self,
        pet_x: int | None = None,
        pet_y: int | None = None,
    ) -> None:
        panel = self.study_panel
        if panel is None or not panel.winfo_exists():
            return
        if pet_x is None:
            pet_x = self.root.winfo_x()
        if pet_y is None:
            pet_y = self.root.winfo_y()
        panel_x, panel_y = study_panel_position(
            pet_x,
            pet_y,
            self.size,
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight(),
        )
        panel.geometry(
            f"{STUDY_PANEL_WIDTH}x{STUDY_PANEL_HEIGHT}{panel_x:+d}{panel_y:+d}"
        )

    def _on_study_press(self, event: tk.Event) -> None:
        self.study_drag_origin = (
            int(event.x_root),
            int(event.y_root),
            self.root.winfo_x(),
            self.root.winfo_y(),
        )

    def _on_study_drag(self, event: tk.Event) -> None:
        if self.study_drag_origin is None:
            return
        start_x, start_y, pet_x, pet_y = self.study_drag_origin
        next_x = pet_x + int(event.x_root) - start_x
        next_y = pet_y + int(event.y_root) - start_y
        self.root.geometry(f"{next_x:+d}{next_y:+d}")
        self._position_study_panel(next_x, next_y)
        self._position_event_countdown(next_x, next_y)

    def _on_study_release(self, _event: tk.Event) -> None:
        if self.study_drag_origin is not None:
            self._persist_config()
        self.study_drag_origin = None

    def _show_study_panel(self) -> None:
        self.show_pet()
        if self.study_session is None:
            self.start_study_session()
            return
        self._ensure_study_panel()
        self._position_study_panel()
        self._update_study_panel()

    def _schedule_study_tick(self) -> None:
        if self.study_job is not None:
            self.root.after_cancel(self.study_job)
        self.study_job = self.root.after(1000, self._study_tick)

    def _study_tick(self) -> None:
        self.study_job = None
        session = self.study_session
        if session is None or not session.active:
            return
        before = session.elapsed_seconds
        completed = session.tick()
        try:
            self.journal.record_focus(session.elapsed_seconds - before)
        except OSError as exc:
            self.journal.error = f"学习记录保存失败：{exc}"
        self._update_study_panel()
        if completed:
            self._finish_study(True)
        else:
            self._schedule_study_tick()

    def _toggle_study_pause(self) -> None:
        session = self.study_session
        if session is None or not session.active:
            return
        paused = session.toggle_pause()
        self._flush_journal()
        self.set_state("idle" if paused else "work", return_to_idle=False)
        self._update_study_panel()

    def _update_study_panel(self) -> None:
        session = self.study_session
        if session is None:
            return
        self.study_goal_var.set(f"本轮目标：{session.goal}")
        self.study_time_var.set(format_duration(session.remaining_seconds))
        if session.completed:
            message = "完成啦！起来活动一下，本龙勉强允许你休息。"
        elif not session.active:
            message = "本轮监督已结束，下次再继续。"
        elif session.paused:
            message = "暂停中。休息一下可以，可别偷偷跑掉。"
        else:
            stage = min(session.elapsed_seconds // 300, len(STUDY_MESSAGES) - 1)
            message = STUDY_MESSAGES[stage]
        self.study_message_var.set(message)
        if self.study_pause_button is not None:
            self.study_pause_button.configure(
                text="继续" if session.paused else "暂停",
                state="normal" if session.active else "disabled",
            )

    def _finish_study(self, completed: bool) -> None:
        session = self.study_session
        if session is None:
            return
        if self.study_job is not None:
            self.root.after_cancel(self.study_job)
            self.study_job = None
        if completed:
            session.finish()
            if not self.study_recorded:
                try:
                    self.journal.record_session()
                except OSError as exc:
                    self.journal.error = str(exc)
                self.study_recorded = True
            self.set_state("victory")
            if self.tray is not None:
                self.tray.notify(
                    "本轮做题完成",
                    f"{session.goal}——辛苦啦，起来活动一下吧。",
                )
            try:
                self.root.bell()
            except tk.TclError:
                pass
        else:
            session.stop()
            self.set_state("idle", return_to_idle=False)
        self._flush_journal()
        self._update_study_panel()

    def _flush_journal(self) -> None:
        if not self.journal.read_only:
            try:
                self.journal.save()
            except OSError as exc:
                self.journal.error = f"学习记录保存失败：{exc}"

    def _stop_study(self) -> None:
        self._finish_study(False)

    def _default_state(self) -> str:
        session = self.study_session
        if session is not None and session.active and not session.paused:
            return "work"
        return "idle"

    def _load_animation(self, state: str) -> LoadedAnimation:
        cached = self.cache.get(state)
        if cached is not None:
            return cached

        path = self.assets.files[state]
        frames: list[ImageTk.PhotoImage] = []
        durations: list[int] = []
        with Image.open(path) as image:
            default_duration = max(40, int(image.info.get("duration", 100)))
            for frame in ImageSequence.Iterator(image):
                prepared = prepare_frame_for_window(
                    frame,
                    self.size,
                    self.transparent_color,
                    self.color_key_enabled,
                )
                frames.append(ImageTk.PhotoImage(prepared, master=self.root))
                durations.append(max(40, int(frame.info.get("duration", default_duration))))

        animation = LoadedAnimation(frames=frames, durations=durations)
        self.cache[state] = animation
        return animation

    def set_state(self, state: str, return_to_idle: bool = True) -> None:
        if state not in self.assets.files:
            raise KeyError(f"未知桌宠状态：{state}")

        if self.animation_job is not None:
            self.root.after_cancel(self.animation_job)
            self.animation_job = None
        if self.return_job is not None:
            self.root.after_cancel(self.return_job)
            self.return_job = None

        if self.size >= LARGE_ANIMATION_SIZE and state != self.state:
            # 超大尺寸下只缓存当前动作，避免七套动画同时占用数 GB 内存。
            self.cache.clear()

        self.state = state
        self.frame_index = 0
        self._draw_next_frame()

        timeout = STATE_TIMEOUTS_MS.get(state)
        if return_to_idle and timeout is not None:
            self.return_job = self.root.after(
                timeout,
                lambda: self.set_state(self._default_state(), return_to_idle=False),
            )

    def _draw_next_frame(self) -> None:
        animation = self._load_animation(self.state)
        index = self.frame_index % len(animation.frames)
        self.label.configure(image=animation.frames[index])
        self.label.image = animation.frames[index]
        self.frame_index = (index + 1) % len(animation.frames)
        self.animation_job = self.root.after(
            animation.durations[index],
            self._draw_next_frame,
        )

    def _on_press(self, event: tk.Event) -> None:
        self.drag_origin = (
            int(event.x_root),
            int(event.y_root),
            self.root.winfo_x(),
            self.root.winfo_y(),
        )
        self.dragged = False

    def _on_drag(self, event: tk.Event) -> None:
        if self.drag_origin is None:
            return
        start_x, start_y, window_x, window_y = self.drag_origin
        dx = int(event.x_root) - start_x
        dy = int(event.y_root) - start_y
        if abs(dx) + abs(dy) > 4:
            self.dragged = True
        next_x = window_x + dx
        next_y = window_y + dy
        self.root.geometry(f"{next_x:+d}{next_y:+d}")
        self._position_study_panel(next_x, next_y)
        self._position_event_countdown(next_x, next_y)

    def _on_release(self, _event: tk.Event) -> None:
        if not self.dragged:
            self.set_state("pet")
        else:
            self._persist_config()
        self.drag_origin = None

    def _show_menu(self, event: tk.Event) -> None:
        try:
            self.menu.tk_popup(int(event.x_root), int(event.y_root))
        finally:
            self.menu.grab_release()

    def _schedule_random_action(self) -> None:
        if not self.random_actions:
            return
        delay = random.randint(self.random_min_ms, self.random_max_ms)
        self.random_job = self.root.after(delay, self._run_random_action)

    def _run_random_action(self) -> None:
        studying = self.study_session is not None and self.study_session.active
        if self.state == "idle" and not studying:
            self.set_state(random.choice(("wave", "work", "eat", "sleep")))
        self._schedule_random_action()

    def _persist_config(self) -> None:
        if self.config_path is None:
            return
        self.config.update(
            {
                "size": self.size,
                "x": self.root.winfo_x(),
                "y": self.root.winfo_y(),
                "event_countdown": (
                    self.event_countdown.to_config(self.countdown_enabled.get())
                    if self.event_configured else {"enabled": False}
                ),
            }
        )
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(self.config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            # 配置保存失败不应导致桌宠退出。
            pass

    def close(self) -> None:
        if self.calendar_panel is not None and self.calendar_panel.window.winfo_exists():
            if self.calendar_panel.dirty and not self.calendar_panel.save():
                return
            self.calendar_panel.destroy()
        self._flush_journal()
        self._persist_config()
        if self.tray is not None:
            self.tray.stop()
        for job in (
            self.animation_job,
            self.return_job,
            self.random_job,
            self.study_job,
            self.question_poll_job,
            self.countdown_job,
        ):
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        self.root.destroy()
