# 小龙娘桌宠 · Windows 64 位免 Python 版

## 运行

本发行包包含单文件“**小龙娘.exe**”：Python、Tk、所需第三方库和七段动画已内置。
使用者不需要安装 Python、Pillow 或 pystray，也不需要运行 run.bat。
请完整解压 ZIP 后双击“小龙娘.exe”。程序不需要管理员权限；请勿默认用管理员身份启动。

桌宠在桌面显示，托盘可显示/隐藏、打开做题监督和答题卡、彻底退出。
如果已有一只桌宠在运行，请先从托盘退出，避免重复启动。

## 操作

- 左键拖动：移动；单击摸头、双击招手。
- Ctrl + 滚轮、右键“调整大小”：调整显示尺寸。
- 右键“开始专注”：填写目标和时长；“专注控制”中暂停、继续或结束。
- 右键“互动动作”：七种动作合并为子菜单。
- 右键“日期倒计时”：设置名称、日期与显示开关。
- 右键或托盘“学习日历与小结”：切换月份，查看专注时长、题目状态和卡点，补记题数与复盘备注。
- Esc：隐藏到托盘；托盘“退出”才是真正关闭。

首次打开没有赛事预设、题单、答题记录或日历历史。通用倒计时和答题卡功能仍然保留，
但需要使用者自行设置日期或导入自己的题单。
已有旧版数据的电脑会继续读取自己的记录，仅自动移除旧版内置的私人赛事预设；
其余自定义提醒、答题记录与学习日历不删除。也可在日期倒计时子菜单中手动“清除提醒”。

## 配置、答题数据与日志

EXE 版用户数据默认存于：

```text
%LOCALAPPDATA%\LittleDragonDesktopPet\
  config.json
  data\question_inbox.json
  data\question_state.json
  data\question_outbox.json
  data\returns\
  data\daily_journal.json
  logs\startup.log
```

可在资源管理器地址栏输入“%LOCALAPPDATA%\LittleDragonDesktopPet”查看。
这些文件不写到 EXE 的临时解包目录，关闭或更新程序后仍会保留。
升级前可备份该目录；不要公开自己的题单、备注、回执或含隐私的日志。

外部工具可按源码仓库 CODEX_BRIDGE.md 的 JSON 协议，向上述 data 目录写入题单，
桌宠会自动读取；全部确认后从答题卡导出回执。不需要桌宠连接任何 AI API。
发行包未附带用户题单、运行配置或 API 凭据。

## 每日小结

监督倒计时推进时自动记录专注秒数，暂停不计；结束或退出保留已用时长。
答题卡状态变更自动汇入当日统计，同一题反复保存不重复加题数。
“额外补记”只填写答题卡以外的完成/不会题数，避免手动重复计算。
复盘可记录当天卡点和下一步计划；切换日期、关闭日历时自动保存。
“复制当日小结”只复制文字，不联网或自动发送。
日历按 UTC+8 归档，每 15 秒及暂停/结束/退出时落盘，异常崩溃可能损失最近不足 15 秒。

## 排错与自检

首次打开单文件 EXE 会先解包运行时，可能比后续启动慢。
后台启动异常会弹窗，详细信息记录到上述 logs\startup.log。

可用 PowerShell 自检并把结果写到指定文件（不启动常驻桌宠）：

```powershell
Start-Process -FilePath ".\小龙娘.exe" -ArgumentList '--check --report-file "startup-check.json"' -WindowStyle Hidden -Wait
Get-Content .\startup-check.json
```

本构建未进行数字签名。Windows 或安全软件可能提示未知发布者；
应核对下载来源和 BUILD_INFO.json 的校验值，不建议关闭安全软件或忽略来源不明的告警。
只验证了 Windows 64 位环境，未承诺所有 Windows 版本、硬件或安全软件配置都兼容。

## 许可、素材与构建

程序代码为 MIT，素材根据维护者说明参考 B 站 ZipZipPipe 形象，经 AI 生成／编辑制作。
来源署名不代表原形象权利人的授权；图片不纳入代码 MIT，见 ASSETS.md。
依赖自身的许可见 THIRD_PARTY_LICENSES；pystray 的未修改 Python 源码见 THIRD_PARTY_SOURCES。

源码仓库提供 scripts/build_windows.py 与 desktop_pet/requirements-build.txt，
可用相同依赖或修改后的 pystray 源码重新构建。生成 EXE 不代表源码不公开。
建议把本 ZIP 上传至 GitHub Releases，把程序源码和构建脚本提交到仓库；
不提交 build、dist、.venv 或个人用户数据。
