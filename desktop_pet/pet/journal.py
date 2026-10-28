"""Local-only daily activity. No bundled history, network, or external analytics."""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Callable

from .countdown import shanghai_today
from .question_bank import QuestionBank, STATUS_LABELS, _write_json_atomic


class DailyJournal:
    def __init__(self, path: Path, today: Callable[[], date] = shanghai_today) -> None:
        self.path = path
        self.today = today
        self.error: str | None = None
        self.read_only = False
        self.payload: dict = {"schema_version": 1, "days": {}, "question_status": {}}
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._validate(data)
                self.payload = data
            except (OSError, ValueError, TypeError, KeyError) as exc:
                # Do not silently overwrite damaged or future-version user records.
                self.error = f"学习记录无法读取，原文件未改动：{exc}"
                self.read_only = True
        self.pending_seconds = 0

    @staticmethod
    def _validate(data: object) -> None:
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("不支持的学习记录格式")
        if not isinstance(data.get("days"), dict) or not isinstance(data.get("question_status"), dict):
            raise ValueError("学习记录结构无效")
        for key, entry in data["days"].items():
            date.fromisoformat(key)
            if not isinstance(entry, dict):
                raise ValueError("每日记录无效")
            for field in ("focus_seconds", "sessions", "manual_done", "manual_stuck"):
                value = entry.get(field, 0)
                if type(value) is not int or value < 0:
                    raise ValueError("统计值无效")
                entry.setdefault(field, 0)
            if not isinstance(entry.get("note", ""), str) or not isinstance(entry.get("questions", {}), dict):
                raise ValueError("每日备注或题目无效")
            for question in entry.get("questions", {}).values():
                if not isinstance(question, dict) or question.get("status") not in STATUS_LABELS:
                    raise ValueError("题目状态无效")
                if not all(isinstance(question.get(field, ""), str) for field in ("title", "note")):
                    raise ValueError("题目备注无效")
                question.setdefault("title", "")
                question.setdefault("note", "")
            entry.setdefault("note", "")
            entry.setdefault("questions", {})
        if any(status not in STATUS_LABELS for status in data["question_status"].values()):
            raise ValueError("最近题目状态无效")

    def _day(self, day: date | None = None) -> dict:
        key = (day or self.today()).isoformat()
        return self.payload["days"].setdefault(key, {
            "focus_seconds": 0, "sessions": 0, "manual_done": 0,
            "manual_stuck": 0, "note": "", "questions": {},
        })

    def save(self) -> None:
        if self.read_only:
            raise OSError(self.error or "学习记录只读")
        _write_json_atomic(self.path, self.payload)
        self.pending_seconds = 0
        self.error = None

    def record_focus(self, seconds: int, day: date | None = None) -> None:
        if self.read_only or seconds <= 0:
            return
        self._day(day)["focus_seconds"] += int(seconds)
        self.pending_seconds += int(seconds)
        if self.pending_seconds >= 15:
            self.save()

    def record_session(self, day: date | None = None) -> None:
        if not self.read_only:
            self._day(day)["sessions"] += 1
            self.save()

    def record_bank(self, bank: QuestionBank | None) -> None:
        if bank is None or self.read_only:
            return
        changed = False
        for question in bank.questions:
            identity = json.dumps([bank.set_id, question.id], ensure_ascii=False)
            key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            previous = self.payload["question_status"].get(key, "pending")
            day_entry = self.payload["days"].get(self.today().isoformat(), {})
            exists_today = key in day_entry.get("questions", {})
            # Merely importing old cards or reopening the calendar is not new work.
            if question.status != previous or exists_today:
                self._day()["questions"][key] = {
                    "status": question.status, "title": question.title, "note": question.note,
                }
                changed = True
            self.payload["question_status"][key] = question.status
        if changed:
            self.save()

    def prime_bank(self, bank: QuestionBank | None) -> None:
        """Remember imported states without assigning historical work to today."""
        if bank is None or self.read_only:
            return
        for question in bank.questions:
            identity = json.dumps([bank.set_id, question.id], ensure_ascii=False)
            key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            self.payload["question_status"][key] = question.status
        self.save()

    def set_manual(self, day: date, done: int, stuck: int, note: str) -> None:
        if type(done) is not int or type(stuck) is not int or not (0 <= done <= 9999 and 0 <= stuck <= 9999):
            raise ValueError("补记题数请输入 0～9999 的整数")
        if len(note) > 10000:
            raise ValueError("每日备注最多 10000 字")
        if self.read_only:
            raise OSError(self.error or "学习记录只读")
        entry = self._day(day)
        entry.update(manual_done=done, manual_stuck=stuck, note=note)
        self.save()

    def summary(self, day: date) -> dict:
        entry = self.payload["days"].get(day.isoformat(), {})
        questions = list(entry.get("questions", {}).values())
        counts = {status: sum(q["status"] == status for q in questions) for status in STATUS_LABELS}
        return {
            "focus_seconds": entry.get("focus_seconds", 0),
            "sessions": entry.get("sessions", 0),
            "done": counts["done"] + entry.get("manual_done", 0),
            "stuck": counts["stuck"] + entry.get("manual_stuck", 0),
            "unsure": counts["unsure"], "skipped": counts["skipped"],
            "manual_done": entry.get("manual_done", 0), "manual_stuck": entry.get("manual_stuck", 0),
            "note": entry.get("note", ""),
            "blockers": [q for q in questions if q["status"] in ("stuck", "unsure")],
        }

    def has_activity(self, day: date) -> bool:
        item = self.summary(day)
        return any(item[key] for key in ("focus_seconds", "sessions", "done", "stuck", "unsure", "skipped", "note"))

    def markdown(self, day: date) -> str:
        item = self.summary(day)
        minutes, seconds = divmod(item["focus_seconds"], 60)
        lines = [
            f"学习小结 · {day.isoformat()}",
            f"专注 {minutes} 分 {seconds} 秒 · 完成监督 {item['sessions']} 轮",
            f"完成 {item['done']} 题 · 不会 {item['stuck']} · 存疑 {item['unsure']} · 跳过 {item['skipped']}",
        ]
        if item["blockers"]:
            lines.append("\n待复盘")
            lines.extend(f"- {q['title']}：{q['note'] or '尚未填写卡点'}" for q in item["blockers"])
        if item["note"]:
            lines.extend(["\n我的复盘", item["note"]])
        return "\n".join(lines)
