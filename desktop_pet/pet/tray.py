from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from queue import Empty, Queue
import tkinter as tk

from PIL import Image


TRAY_ICON_SIZE = 64


def make_tray_image(source: Path) -> Image.Image:
    with Image.open(source) as image:
        frame = image.convert("RGBA")
    bounds = frame.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError(f"托盘图标没有可见像素：{source}")
    sprite = frame.crop(bounds)
    sprite.thumbnail((56, 56), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (TRAY_ICON_SIZE, TRAY_ICON_SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(
        sprite,
        ((TRAY_ICON_SIZE - sprite.width) // 2, (TRAY_ICON_SIZE - sprite.height) // 2),
    )
    return canvas


class TrayController:
    """把托盘线程的操作排队，再由 Tk 主线程安全执行。"""

    def __init__(
        self,
        root: tk.Tk,
        image: Image.Image,
        callbacks: dict[str, Callable[[], None]],
    ) -> None:
        try:
            import pystray
        except ImportError as exc:
            raise RuntimeError("缺少 pystray，请先安装 requirements.txt") from exc

        self.root = root
        self.callbacks = callbacks
        self.actions: Queue[str] = Queue()
        self.poll_job: str | None = None
        self.stopped = False
        self.icon = pystray.Icon(
            "little_dragon_pet",
            image,
            "小龙娘桌宠",
            menu=pystray.Menu(
                pystray.MenuItem(
                    "显示 / 隐藏小龙娘",
                    self._queue_handler("toggle_pet"),
                    default=True,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "开始专注…",
                    self._queue_handler("start_study"),
                ),
                pystray.MenuItem(
                    "学习日历与小结",
                    self._queue_handler("calendar"),
                ),
                pystray.MenuItem(
                    "答题卡",
                    self._queue_handler("question_cards"),
                ),
                pystray.MenuItem(
                    "专注控制",
                    pystray.Menu(
                        pystray.MenuItem("显示专注面板", self._queue_handler("show_study")),
                        pystray.MenuItem("暂停 / 继续专注", self._queue_handler("toggle_study_pause")),
                    ),
                ),
                pystray.MenuItem(
                    "日期倒计时",
                    self._queue_handler("countdown"),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._queue_handler("exit")),
            ),
        )

    def _queue_handler(self, action: str) -> Callable[..., None]:
        def handler(*_args: object) -> None:
            if not self.stopped:
                self.actions.put(action)

        return handler

    def start(self) -> None:
        self.icon.run_detached()
        self.poll_job = self.root.after(100, self._drain_actions)

    def _drain_actions(self) -> None:
        self.poll_job = None
        while not self.stopped:
            try:
                action = self.actions.get_nowait()
            except Empty:
                break
            callback = self.callbacks.get(action)
            if callback is not None:
                callback()
        if not self.stopped:
            self.poll_job = self.root.after(100, self._drain_actions)

    def notify(self, title: str, message: str) -> None:
        if self.stopped:
            return
        try:
            self.icon.notify(message, title)
        except (NotImplementedError, OSError):
            pass

    def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        if self.poll_job is not None:
            try:
                self.root.after_cancel(self.poll_job)
            except tk.TclError:
                pass
            self.poll_job = None
        self.icon.stop()
