# Codex ↔ 小龙娘答题卡桥接

## 数据目录

下文的 `data/` 相对于当前运行的数据根目录：源码版为 `desktop_pet/`，
EXE 版为 `%LOCALAPPDATA%\LittleDragonDesktopPet\`。
若设置 `LITTLE_DRAGON_DATA_DIR`，则以该目录为准。不要向 EXE 的临时解包目录写入题单。

桥接脚本需要 Python，但桌宠 EXE 本身不需要。外部工具也可以直接按协议读写 JSON。
在源码仓库根目录，向 EXE 版推送的示例为：

```powershell
.\.venv\Scripts\python.exe desktop_pet\scripts\question_bridge.py --data-dir "$env:LOCALAPPDATA\LittleDragonDesktopPet" push desktop_pet\examples\question_bank.example.json
.\.venv\Scripts\python.exe desktop_pet\scripts\question_bridge.py --data-dir "$env:LOCALAPPDATA\LittleDragonDesktopPet" pull
```

## Codex 下发题单

当用户要求“把推荐题单同步给桌宠”时，将符合
`examples/question_bank.example.json` 结构的 JSON 原子写入：

`data/question_inbox.json`

也可以使用桥接命令：

```powershell
python scripts\question_bridge.py push <题单.json>
```

每个题单使用新的 `set_id`，每道题的 `id` 在题单内唯一。不要覆盖桌宠维护的
`status` 和 `note`，除非用户明确要求重置进度。

桌宠每两秒检查一次收件箱。新题单只触发托盘通知，不会抢占用户当前窗口。

## 桌宠返回结果

用户为每道题确认“完成 / 不会 / 存疑 / 跳过”后，桌宠会写入：

`data/question_outbox.json`

历史回执位于：

`data/returns/`

当用户要求“读取桌宠答题卡结果”时，Codex 应读取最新 outbox，优先处理
`stuck`、`unsure` 和 `skipped`，并结合每题 `note` 继续讲解或生成下一轮题单。

读取命令：

```powershell
python scripts\question_bridge.py pull
```

桌宠同时会把 Markdown 摘要复制到剪贴板，供用户手动粘贴回当前 Codex 对话。

## 边界

当前桥接不调用未公开的 Codex 内部接口，也不会冒充用户向对话自动发消息。
如需免口令的工具调用，可在此文件协议之上增加本地 MCP 工具；题单和回执结构无需改变。
