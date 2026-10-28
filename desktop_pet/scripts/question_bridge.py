from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from pet.question_bank import push_question_bank  # noqa: E402
from pet.runtime import runtime_paths  # noqa: E402


def load_payload(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("题单 JSON 根节点必须是对象")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Codex ↔ 小龙娘答题卡文件桥接")
    parser.add_argument("--data-dir", type=Path,
                        help="运行状态根目录；对接 EXE 时指定其 LocalAppData 目录")
    subparsers = parser.add_subparsers(dest="command", required=True)

    push_parser = subparsers.add_parser("push", help="向桌宠下发一个题单 JSON")
    push_parser.add_argument("json_file", type=Path)
    subparsers.add_parser("pull", help="输出桌宠最新答题卡回执")
    subparsers.add_parser("paths", help="显示收件箱和回执路径")

    args = parser.parse_args()
    data_dir = runtime_paths(data_dir=args.data_dir).data
    if args.command == "push":
        path = push_question_bank(data_dir, load_payload(args.json_file))
        print(path.resolve())
    elif args.command == "pull":
        path = data_dir / "question_outbox.json"
        if not path.is_file():
            raise SystemExit("暂无桌宠答题卡回执")
        print(path.read_text(encoding="utf-8"), end="")
    else:
        print(f"inbox={data_dir / 'question_inbox.json'}")
        print(f"outbox={data_dir / 'question_outbox.json'}")


if __name__ == "__main__":
    main()
