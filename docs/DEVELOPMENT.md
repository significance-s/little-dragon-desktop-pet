# 源码安装与开发

日常使用建议下载 [Windows x64 EXE 发行包](https://github.com/significance-s/little-dragon-desktop-pet/releases/latest)。
本文面向需要修改代码、排查源码启动问题或自行构建的开发者。

## 环境与安装

支持 Windows、Python 3.12 / 3.13。安装 Python 时保留 pip、Tcl/Tk 和 Python Launcher。
完整解压或克隆仓库后，将项目放在当前用户可写的目录，从项目根目录执行：

~~~powershell
.\run.bat --setup
.\run.bat --check
.\run.bat
~~~

启动器在根目录创建隔离的 .venv，安装 desktop_pet/requirements.txt 中的依赖，
不向系统 Python 安装第三方库。首次安装需要联网；后续正常运行不需要联网。
--setup 只准备环境，--check 检查配置、动画、Tk 和托盘，不启动常驻实例。

也可指定 Python 版本：

~~~powershell
py -3.13 desktop_pet\bootstrap.py --setup
.\.venv\Scripts\python.exe desktop_pet\launch.py
~~~

使用 Python 3.12 时，将第一条命令的 -3.13 替换为 -3.12。

## 配置与数据

源码版读取 desktop_pet/config.json；首次没有此文件时使用 config.example.json。
学习记录与答题文件位于 desktop_pet/data/，启动错误日志位于 desktop_pet/logs/。
以上本机文件均不应提交到版本库。

EXE 版默认使用 %LOCALAPPDATA%\LittleDragonDesktopPet。
LITTLE_DRAGON_DATA_DIR 环境变量可指定其他数据根目录；
答题桥接脚本另支持 --data-dir，详见 [文件协议](../desktop_pet/CODEX_BRIDGE.md)。

## 测试与自检

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s desktop_pet\tests -v
~~~

GUI 测试需要可创建 Tk 窗口的环境。完整应用自检必须指定专用数据目录，不能指向真实学习记录：

~~~powershell
.\.venv\Scripts\python.exe desktop_pet\launch.py --self-test --data-dir build\qa\smoke-state --report-file build\qa\smoke-report.json
~~~

自检会写入合成题单、备注和日历记录，然后自动退出。报告应为 ok: true。

## 故障排查

- 找不到 Python：确认安装了受支持版本及 Launcher；Microsoft Store 命令别名不等于完整 Python。
- 依赖下载失败：检查网络和包索引连接，再运行 run.bat --setup。
- 虚拟环境损坏或项目搬过位置：退出桌宠，将 .venv 重命名为 .venv.old，再运行 --setup 重建。不要复制其他项目的虚拟环境。
- Permission denied：检查项目与临时目录权限，避免将项目放在受保护目录；无需默认使用管理员身份运行。
- 需要控制台错误：直接执行 .venv 中的 python.exe desktop_pet\launch.py。

## 构建与素材

[Windows EXE 构建说明](BUILD_WINDOWS.md) 包含构建命令、输出文件和打包检查。
运行时动画位于 pic/gif/，动作关键姿势位于 pic/动作差分/。

~~~powershell
.\.venv\Scripts\python.exe scripts\make_action_gifs.py
~~~

此命令会覆盖对应动画文件，执行前应保留需要的版本。
动画是关键姿势驱动的轻量循环，不是 Live2D 骨骼动画。

代码与图像的许可范围不同，见 [LICENSE](../LICENSE) 和 [ASSETS.md](../ASSETS.md)。
