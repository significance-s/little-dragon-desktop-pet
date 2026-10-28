# 小龙娘桌宠

一个 Windows 桌面陪伴程序：原画风透明动画、系统托盘、做题监督、日期倒计时和答题卡。
使用 Python、Tkinter、Pillow 与 pystray，不依赖 Electron、Live2D 或在线 AI API。

![待机动画](pic/gif/00_待机母版.gif)

> **普通使用推荐 [Windows x64 EXE 发行包](https://github.com/significance-s/little-dragon-desktop-pet/releases/latest)**：完整解压下载的 ZIP，
> 双击其中的 `小龙娘.exe`，不需要安装 Python 或第三方依赖。
> 在 [GitHub Releases](https://github.com/significance-s/little-dragon-desktop-pet/releases) 下载免 Python 版；仓库的 Code → Download ZIP 是源码，不包含 EXE。
> 详见 [EXE 使用说明](docs/WINDOWS_RELEASE.md)；源码安装流程见下文。

## 功能

- 七种透明 APNG 动作：待机、招手、工作、吃饭、睡觉、胜利、摸头，512×512、10～14 帧。
- 左键拖动、点击互动、128～2048 px 大小调节；待机不持续缩放。
- 系统托盘显示/隐藏、通知、彻底退出。
- 做题监督：目标、分钟倒计时、暂停/继续、完成反馈；面板随形象移动。
- 日期倒计时：自定义名称和目标日期，按上海日历自动跨天更新。
- 本地答题卡：逐题状态、备注保存、回执导出、剪贴板摘要。
- 学习日历：按月查看专注时长、完成题数与卡点；支持补记题数、每日复盘和复制小结。
- 干净初始配置：不预设赛事或个人日期，不附带题单、答题记录或日历历史。

## 源码版第一次安装

### 1. 安装基础运行时

当前以 Windows 64 位环境为验证目标；Python 支持版本为 **3.12、3.13**。

从 [Python 官方 Windows 下载页](https://www.python.org/downloads/windows/) 安装对应版本。
安装器中保留 **pip、Tcl/Tk 与 IDLE、Python Launcher** 组件；建议勾选 **Add Python to PATH**。
Tkinter 属于 Python 的 Tcl/Tk 组件，不能通过安装 Pillow 来替代。

打开终端检查，以下任一命令能正常输出对应版本即可：

~~~powershell
py -3.13 --version
# 如果安装的是 3.12：
py -3.12 --version
# 也支持 PATH 中的 Python：
python --version
~~~

### 2. 下载并完整解压项目

在 GitHub 仓库点击 **Code → Download ZIP**，解压整个压缩包；
不要直接在压缩包里双击，也不要只复制启动脚本。

将项目放在自己有写入权限的目录。不建议直接放在 Program Files 等受保护目录。
仓库不携带作者电脑的 Python、虚拟环境、个人配置或答题记录。

### 3. 双击启动

双击项目根目录的 **run.bat**。

首次启动会：

1. 找到受支持的基础 Python。
2. 在项目根目录创建隔离的 .venv，不启用系统 site-packages。
3. 从 desktop_pet/requirements.txt 安装依赖并检查安装是否完整。
4. 用该 .venv 中的解释器启动桌宠。

**不会回退到全局 Pillow/pystray，也不会往系统 Python 安装第三方包。**
首次安装需要能访问 Python 包索引；不要在安装完成前关闭控制台。
准备完成后，后续启动通常不需联网；依赖文件变化或环境不完整时会再次安装。

源码运行需要 Python 是明确的安装前提，不是默认你的电脑已经有作者的开发环境。

## 安装检查与手动运行

以下命令均从解压后的项目根目录执行，不需要激活虚拟环境或修改 PowerShell 执行策略。

只准备项目环境，不打开桌宠：

~~~powershell
.\run.bat --setup
~~~

检查已经准备好的环境（不联网安装、不启动常驻桌宠；会短暂测试托盘图标）：

~~~powershell
.\run.bat --check
~~~

也可指定 Python 版本直接执行：

~~~powershell
py -3.13 desktop_pet\bootstrap.py --setup
# 或 py -3.12 desktop_pet\bootstrap.py --setup

.\.venv\Scripts\python.exe desktop_pet\launch.py
~~~

需要查看完整控制台报错时：

~~~powershell
.\.venv\Scripts\python.exe desktop_pet\app.py
~~~

## 使用方式

| 操作 | 效果 |
| --- | --- |
| 左键拖动形象 | 移动桌宠；监督和日期面板同步跟随 |
| 单击 / 双击 | 摸头 / 招手 |
| Ctrl + 滚轮 | 调整大小；右键菜单支持手动输入 |
| 右键 → 开始专注 | 设置目标与本轮时长 |
| 右键 → 专注控制 | 显示面板、暂停/继续、完成或结束本轮 |
| 右键 → 互动动作 | 选择七种动作，主菜单不再纵向展开所有动作 |
| 右键 → 日期倒计时 | 设置名称、日期及显示开关 |
| 拖动面板文字 | 带着桌宠一起移动 |
| Esc / 隐藏到托盘 | 隐藏形象；做题计时继续 |
| 托盘 → 显示/隐藏 | 恢复或隐藏形象 |
| 托盘 → 退出 | 真正关闭程序 |

测试新版前请从托盘退出旧实例，避免同时启动多只桌宠。

日期提醒优先停靠在脚边，底部空间不足时移到头顶。
按 UTC+8 日历日期相减：目标当天显示“就是今天！”，之后显示已过去的天数。
默认关闭日期倒计时，不预设任何赛事；首次启用时自行填写提醒名称和日期。
旧版内置的私人赛事预设在加载配置时自动移除，不仅关闭显示，还删除其名称和日期；
自己设置的其他提醒不受影响。也可从“日期倒计时 → 清除提醒”彻底删除当前提醒。

## 学习日历与每日小结

右键或托盘选择 **学习日历与小结**。左右箭头切换月份，点日期查看当日统计，
“今天”回到当前日期；日期下方的点表示有记录。日历不会在晚上自动弹出打断工作。

- 专注时长来自监督倒计时实际推进的秒数，暂停不计；提前结束只记已用时间，不按计划时长补满。
- 自动归档答题卡的状态变更和卡点；同一题单/题目一天内反复保存不会重复计数，改状态会修正当日统计。
- 导入已完成题单、启动时读取旧状态，不当作当天新完成题目。
- “额外补记”用于不在答题卡里的题目；保存的是当日总补记数，不是每按一次再累加。
- 复盘备注切换日期或关闭日历时自动保存，也可点击“保存复盘”或按 Ctrl+S。
- “复制当日小结”生成文本，供手动粘贴；不自动发消息或联网同步。

数据使用 UTC+8 日历日期，位于本机 data/daily_journal.json。
计时每 15 秒落盘，暂停、结束和退出时也会保存；异常崩溃可能损失最近不足 15 秒。
文件损坏时保留原文件并提示，不静默清空；建议升级前备份本机数据目录。

## 配置与个人数据

首次运行读取公开模板 desktop_pet/config.example.json。
调整大小、位置或提醒等操作会保存到 desktop_pet/config.json；
个人配置和 desktop_pet/data/ 中的答题数据已加入 Git 忽略规则。

**EXE 版**的配置和答题数据保存在 `%LOCALAPPDATA%\LittleDragonDesktopPet\`，
不写入单文件解压的临时资源目录。`LITTLE_DRAGON_DATA_DIR` 环境变量可指定另一数据目录。
以下表格描述的是源码版路径。

| 文件/目录 | 用途 |
| --- | --- |
| desktop_pet/config.example.json | 随仓库提供的无个人坐标配置模板 |
| desktop_pet/config.json | 本机运行配置，自动保存、不提交 |
| desktop_pet/data/question_inbox.json | 推荐题单收件箱 |
| desktop_pet/data/question_state.json | 答题进度和备注 |
| desktop_pet/data/question_outbox.json | 最新回执 |
| desktop_pet/data/returns/ | 历史回执 |
| desktop_pet/data/daily_journal.json | 本机学习日历、题目统计和复盘备注，不提交 |
| desktop_pet/logs/startup.log | 后台启动错误日志 |
| .venv/ | 本项目专用依赖环境，不提交、不随 ZIP 分发 |

## 推荐题单与答题回执

桌宠不直接连接 Codex 或其他 AI 服务，不需要 API Key。
文件桥接不会自动替用户向对话发消息；外部工具可按本地 JSON 协议交换数据。

准备好项目环境后，运行仓库内的示例：

~~~powershell
.\.venv\Scripts\python.exe desktop_pet\scripts\question_bridge.py push desktop_pet\examples\question_bank.example.json
.\.venv\Scripts\python.exe desktop_pet\scripts\question_bridge.py pull
~~~

从桌宠菜单打开答题卡，标记“完成 / 不会 / 存疑 / 跳过”并记录备注。
全部确认后提交，会写入回执并复制 Markdown 摘要，供手动粘贴回对话。
协议详见 [CODEX_BRIDGE.md](desktop_pet/CODEX_BRIDGE.md)。

## 常见问题

**提示没有受支持的 Python？**
安装 Python 3.12 或 3.13，并保留 Launcher 与 Tcl/Tk 组件。
修改 PATH 后重新打开终端；只有 Microsoft Store 的 python 命令别名不代表已经装好 Python。

**下载依赖超时或连接失败？**
首次安装需要联网。检查包索引连通性、代理或防火墙，再运行 run.bat --setup。
失败不会被记为安装完成，也不会偷偷改用全局包。

**提示 Permission denied？**
把整个项目解压到自己可写的目录，检查当前账户对项目和系统临时目录的访问权限。
不要把“用管理员权限跑一次”作为默认安装步骤。

**已有 .venv 却仍提示环境不完整？**
启动器会检查隔离设置、依赖导入和依赖文件摘要，不只判断目录是否存在。
先退出桌宠；如果该虚拟环境已损坏或随项目移动过，将项目内的 .venv 重命名为 .venv.old，
再运行 run.bat --setup 重新创建。不要复制别人的虚拟环境。
参考 [Python 官方虚拟环境说明](https://docs.python.org/3.13/library/venv.html)。

**双击后没看到形象？**
先检查托盘图标和 start_hidden 配置。后台异常会弹窗并写入 desktop_pet/logs/startup.log；
使用上述控制台命令可直接查看报错。反馈问题时附 Python 版本、启动错误，
不要公开个人题单、备注或包含隐私的日志内容。

**可以在没有 Python 的电脑上运行吗？**
可以使用 Windows x64 EXE 发行包；Python、Tk、依赖和七段动画已经一起打包。
源码版仍需要先安装 Python。EXE 暂未数字签名；不要关闭杀毒软件，遇到拦截请核对来源并反馈。

## 开发、测试与素材重建

在干净项目中使用与普通用户相同的安装流程：

~~~powershell
.\run.bat --setup
.\.venv\Scripts\python.exe -m unittest discover -s desktop_pet\tests -v
~~~

GUI 测试需要可创建 Tk 窗口的环境。Windows CI 同样先创建项目虚拟环境，再运行测试；
本地验证不代表远端 CI 已运行。

生成免 Python 的 EXE 与发行 ZIP，见 [Windows 构建说明](docs/BUILD_WINDOWS.md)。
生成的 `build/`、`dist/` 不进入 Git；发行 ZIP 上传 GitHub Releases。

运行时素材位于 pic/gif/*.apng，动作关键姿势位于 pic/动作差分/*.png。
重建动画：

~~~powershell
.\.venv\Scripts\python.exe scripts\make_action_gifs.py
~~~

重建会覆盖对应 APNG/GIF/WebP，请先保留需要的素材版本。
这是关键姿势驱动的轻量循环动画，不是 Live2D 骨骼动画。

## 目录

~~~text
run.bat                      Windows 启动入口
desktop_pet/bootstrap.py     安装、隔离环境检查与启动
desktop_pet/launch.py        启动自检、后台错误提示和日志
desktop_pet/app.py           桌宠主程序
desktop_pet/pet/             动画、托盘、监督、倒计时、答题卡
desktop_pet/tests/           自动测试
desktop_pet/examples/        公开题单示例
pic/gif/                    运行时 APNG 与 README 预览
pic/动作差分/                动画重建源图
scripts/                    动画重建及 Windows EXE 构建脚本
.github/                    Windows 安装与测试工作流
~~~

## 许可与素材说明

代码、脚本、测试与配套文本采用 [MIT License](LICENSE)，适用范围见
[LICENSE_STATUS.md](LICENSE_STATUS.md)。

根据维护者说明，角色素材根据 **B 站 ZipZipPipe 的形象，经 AI 生成／编辑制作**。
图像不纳入代码的 MIT 授权；上述署名是来源说明，不代表原形象权利人的授权、认可或合作。
具体状态见 [ASSETS.md](ASSETS.md)。

本仓库不包含作者个人题单、答题记录、窗口坐标、API 凭据、Python 缓存、
原始参考图片、生成提示词、原生宠物试验包或调试截图。
示例目录中的题单是人工编写的通用协议样例，不会自动载入；EXE 不打包该样例。
构建时会拒绝带私人预设的模板，并检查 EXE 内无个人运行文件或开发者用户路径。
