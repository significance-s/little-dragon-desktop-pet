from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StudySession:
    goal: str
    total_seconds: int
    remaining_seconds: int = field(init=False)
    paused: bool = False
    active: bool = True
    completed: bool = False

    def __post_init__(self) -> None:
        self.goal = self.goal.strip()
        if not self.goal:
            raise ValueError("做题目标不能为空")
        if self.total_seconds <= 0:
            raise ValueError("监督时长必须大于零")
        self.remaining_seconds = int(self.total_seconds)

    @property
    def elapsed_seconds(self) -> int:
        return self.total_seconds - self.remaining_seconds

    def tick(self, seconds: int = 1) -> bool:
        """推进计时；返回 True 表示本次推进刚好完成。"""
        if not self.active or self.paused:
            return False
        self.remaining_seconds = max(0, self.remaining_seconds - max(0, int(seconds)))
        if self.remaining_seconds == 0:
            self.active = False
            self.completed = True
            return True
        return False

    def toggle_pause(self) -> bool:
        if self.active:
            self.paused = not self.paused
        return self.paused

    def finish(self) -> None:
        self.active = False
        self.completed = True
        self.paused = False

    def stop(self) -> None:
        self.active = False
        self.completed = False
        self.paused = False


def format_duration(seconds: int) -> str:
    minutes, secs = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
