from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import tkinter as tk


SHANGHAI_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
DEFAULT_EVENT_TITLE = "我的目标"


def shanghai_today() -> date:
    """按上海日历计算，不受电脑所在时区或夏令时影响。"""
    return datetime.now(SHANGHAI_TIMEZONE).date()


@dataclass(frozen=True)
class EventCountdown:
    title: str
    target_date: date

    @classmethod
    def parse(cls, title: str, date_text: str) -> EventCountdown:
        title = title.strip()
        if not title or len(title) > 80:
            raise ValueError("名称请输入 1～80 个字符。")
        date_text = date_text.strip()
        try:
            target = date.fromisoformat(date_text)
        except (ValueError, TypeError) as exc:
            raise ValueError("日期请输入 YYYY-MM-DD，例如 2030-01-01。") from exc
        if target.isoformat() != date_text:
            raise ValueError("日期请输入 YYYY-MM-DD，例如 2030-01-01。")
        return cls(title, target)

    @classmethod
    def from_config(cls, value: object) -> EventCountdown:
        if value is None:
            return cls(DEFAULT_EVENT_TITLE, shanghai_today())
        if not isinstance(value, dict):
            raise ValueError("日期倒计时配置必须是对象。")
        title = value.get("title", DEFAULT_EVENT_TITLE)
        target = value.get("date", shanghai_today().isoformat())
        if not isinstance(title, str) or not isinstance(target, str):
            raise ValueError("倒计时名称和日期必须是文本。")
        return cls.parse(title, target)

    def remaining_days(self, today: date | None = None) -> int:
        return (self.target_date - (today if today is not None else shanghai_today())).days

    def status_text(self, today: date | None = None) -> str:
        days = self.remaining_days(today)
        if days > 0:
            return f"还剩 {days} 天"
        if days == 0:
            return "就是今天！"
        return f"已过去 {-days} 天"

    def to_config(self, enabled: bool) -> dict:
        return {"title": self.title, "date": self.target_date.isoformat(), "enabled": enabled}


def countdown_panel_position(
    pet_x: int, pet_y: int, pet_size: int,
    screen_width: int, screen_height: int,
    panel_width: int, panel_height: int,
) -> tuple[int, int]:
    """优先放在脚边；底部不足则置于头顶，最后夹紧到屏幕内。"""
    x = pet_x + (pet_size - panel_width) // 2
    below = pet_y + pet_size + 8
    above = pet_y - panel_height - 8
    if below + panel_height <= screen_height:
        y = below
    elif above >= 0:
        y = above
    else:
        y = screen_height - panel_height
    return (
        min(max(0, x), max(0, screen_width - panel_width)),
        min(max(0, y), max(0, screen_height - panel_height)),
    )


class CountdownPanel:
    """日期提醒卡；时间和显示状态由 PetWindow 管理。"""

    def __init__(
        self, root: tk.Tk, event: EventCountdown, *, always_on_top: bool,
        on_edit: Callable[[], None], on_hide: Callable[[], None],
        on_press: Callable, on_drag: Callable, on_release: Callable,
    ) -> None:
        self.event = event
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.resizable(False, False)
        self.window.attributes("-topmost", always_on_top)
        bg = "#f7f2ff"
        self.window.configure(
            background=bg, highlightbackground="#a890cd", highlightthickness=1,
        )
        self.title_var = tk.StringVar(master=root)
        self.days_var = tk.StringVar(master=root)
        self.date_var = tk.StringVar(master=root)
        # 点数字体在高 DPI 下会变高，因此用内容请求高度，不写死面板高度。
        scaling = float(root.tk.call("tk", "scaling"))
        self.width = max(320, round(320 * scaling / (96 / 72)))
        header = tk.Frame(self.window, background=bg)
        header.pack(fill="x", padx=12, pady=(8, 0))
        badge = tk.Label(header, text="小龙娘 · 日期倒计时", font=("Microsoft YaHei UI", 9),
                         foreground="#7c659d", background=bg, cursor="fleur")
        badge.pack(side="left", fill="x", expand=True)
        self.edit_button = tk.Button(
            header, text="设置", command=on_edit, borderwidth=0,
            background=bg, activebackground="#eadffc", foreground="#655080",
        )
        self.edit_button.pack(side="left", padx=4)
        self.hide_button = tk.Button(
            header, text="×", command=on_hide, borderwidth=0,
            background=bg, activebackground="#eadffc", foreground="#655080",
        )
        self.hide_button.pack(side="right")
        self.title_label = tk.Label(
            self.window, textvariable=self.title_var, font=("Microsoft YaHei UI", 11, "bold"),
            foreground="#514068", background=bg, wraplength=self.width - 36,
            justify="center", cursor="fleur",
        )
        self.title_label.pack(fill="x", padx=16, pady=(6, 0))
        self.days_label = tk.Label(
            self.window, textvariable=self.days_var, font=("Microsoft YaHei UI", 24, "bold"),
            foreground="#715099", background=bg, cursor="fleur",
        )
        self.days_label.pack(padx=12, pady=(1, 0))
        self.date_label = tk.Label(
            self.window, textvariable=self.date_var, font=("Microsoft YaHei UI", 9),
            foreground="#8c7b9f", background=bg, cursor="fleur",
        )
        self.date_label.pack(padx=12, pady=(0, 10))
        for widget in (header, badge, self.title_label, self.days_label, self.date_label):
            widget.bind("<ButtonPress-1>", on_press)
            widget.bind("<B1-Motion>", on_drag)
            widget.bind("<ButtonRelease-1>", on_release)
        self.update()

    def update(self, today: date | None = None) -> None:
        self.title_var.set(f"距离 {self.event.title}")
        self.days_var.set(self.event.status_text(today))
        self.date_var.set(f"{self.event.target_date:%Y.%m.%d} · 上海时间")

    def position(self, pet_x: int, pet_y: int, pet_size: int) -> None:
        self.window.update_idletasks()
        height = self.window.winfo_reqheight()
        x, y = countdown_panel_position(
            pet_x, pet_y, pet_size, self.window.winfo_screenwidth(),
            self.window.winfo_screenheight(), self.width, height,
        )
        self.window.geometry(f"{self.width}x{height}{x:+d}{y:+d}")

    def show(self) -> None:
        # 每次核对日期不应再次抬高窗口，避免周期性打扰其他操作。
        if self.window.state() != "normal":
            self.window.deiconify()
            self.window.lift()

    def hide(self) -> None:
        self.window.withdraw()
