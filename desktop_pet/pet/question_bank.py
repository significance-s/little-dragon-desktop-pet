from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


STATUS_LABELS: dict[str, str] = {
    "pending": "未确认",
    "done": "完成",
    "stuck": "不会",
    "unsure": "存疑",
    "skipped": "跳过",
}


@dataclass
class Question:
    id: str
    title: str
    prompt: str = ""
    difficulty: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = ""
    status: str = "pending"
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Question":
        question_id = str(data.get("id", "")).strip()
        title = str(data.get("title", "")).strip()
        if not question_id or not title:
            raise ValueError("每道题都必须包含非空的 id 和 title")
        status = str(data.get("status", "pending"))
        if status not in STATUS_LABELS:
            status = "pending"
        raw_tags = data.get("tags", [])
        tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
        return cls(
            id=question_id,
            title=title,
            prompt=str(data.get("prompt", "")),
            difficulty=str(data.get("difficulty", "")),
            tags=tags,
            source=str(data.get("source", "")),
            status=status,
            note=str(data.get("note", "")),
        )


@dataclass
class QuestionBank:
    set_id: str
    title: str
    questions: list[Question]
    source: str = "codex"
    created_at: str = ""
    schema_version: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuestionBank":
        if int(data.get("schema_version", 1)) != 1:
            raise ValueError("暂不支持该题库 schema_version")
        set_id = str(data.get("set_id", "")).strip()
        title = str(data.get("title", "")).strip()
        raw_questions = data.get("questions")
        if not set_id or not title or not isinstance(raw_questions, list):
            raise ValueError("题库必须包含 set_id、title 和 questions 数组")
        questions = [Question.from_dict(item) for item in raw_questions]
        if not questions:
            raise ValueError("题库至少需要一道题")
        ids = [question.id for question in questions]
        if len(ids) != len(set(ids)):
            raise ValueError("题目 id 不能重复")
        return cls(
            set_id=set_id,
            title=title,
            questions=questions,
            source=str(data.get("source", "codex")),
            created_at=str(data.get("created_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "set_id": self.set_id,
            "title": self.title,
            "source": self.source,
            "created_at": self.created_at,
            "questions": [asdict(question) for question in self.questions],
        }

    @property
    def confirmed_count(self) -> int:
        return sum(question.status != "pending" for question in self.questions)

    @property
    def all_confirmed(self) -> bool:
        return self.confirmed_count == len(self.questions)

    def summary_counts(self) -> dict[str, int]:
        return {
            status: sum(question.status == status for question in self.questions)
            for status in STATUS_LABELS
        }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON 根节点必须是对象：{path}")
    return data


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class QuestionBankBridge:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.inbox_path = data_dir / "question_inbox.json"
        self.state_path = data_dir / "question_state.json"
        self.outbox_path = data_dir / "question_outbox.json"
        self.history_dir = data_dir / "returns"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.bank: QuestionBank | None = None
        self.last_error: str | None = None
        self._inbox_signature: tuple[int, int] | None = None

    def load_if_changed(self) -> QuestionBank | None:
        if not self.inbox_path.is_file():
            return None
        stat = self.inbox_path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        if signature == self._inbox_signature:
            return None
        self._inbox_signature = signature

        try:
            bank = QuestionBank.from_dict(_read_json(self.inbox_path))
            self._merge_saved_state(bank)
            self.bank = bank
            self.last_error = None
            self.save_state()
            return bank
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.last_error = str(exc)
            return None

    def _merge_saved_state(self, bank: QuestionBank) -> None:
        if not self.state_path.is_file():
            return
        try:
            saved = QuestionBank.from_dict(_read_json(self.state_path))
        except (OSError, ValueError, json.JSONDecodeError):
            return
        if saved.set_id != bank.set_id:
            return
        previous = {question.id: question for question in saved.questions}
        for question in bank.questions:
            old = previous.get(question.id)
            if old is not None:
                question.status = old.status
                question.note = old.note

    def save_state(self) -> None:
        if self.bank is not None:
            _write_json_atomic(self.state_path, self.bank.to_dict())

    def export_result(self) -> Path:
        bank = self.bank
        if bank is None:
            raise ValueError("当前没有题库")
        if not bank.all_confirmed:
            raise ValueError("仍有题目尚未确认状态")

        finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
        payload = bank.to_dict()
        payload["finished_at"] = finished_at
        payload["summary"] = bank.summary_counts()
        _write_json_atomic(self.outbox_path, payload)

        safe_id = re.sub(r"[^0-9A-Za-z._-]+", "_", bank.set_id).strip("_") or "set"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        _write_json_atomic(self.history_dir / f"{stamp}-{safe_id}.json", payload)
        return self.outbox_path

    def markdown_summary(self) -> str:
        bank = self.bank
        if bank is None:
            return ""
        lines = [f"桌宠答题卡回执：{bank.title}", f"题单 ID：{bank.set_id}", ""]
        for index, question in enumerate(bank.questions, start=1):
            status = STATUS_LABELS[question.status]
            line = f"{index}. [{status}] {question.title}"
            if question.note.strip():
                line += f"｜备注：{question.note.strip()}"
            lines.append(line)
        counts = bank.summary_counts()
        lines.extend(
            [
                "",
                "汇总："
                f"完成 {counts['done']}，不会 {counts['stuck']}，"
                f"存疑 {counts['unsure']}，跳过 {counts['skipped']}。",
                "请读取 question_outbox.json，并根据不会、存疑和跳过项继续讲解或推荐。",
            ]
        )
        return "\n".join(lines)


def push_question_bank(data_dir: Path, payload: dict[str, Any]) -> Path:
    """供 Codex 或其他本地脚本原子下发题单。"""
    bank = QuestionBank.from_dict(payload)
    path = data_dir / "question_inbox.json"
    _write_json_atomic(path, bank.to_dict())
    return path
