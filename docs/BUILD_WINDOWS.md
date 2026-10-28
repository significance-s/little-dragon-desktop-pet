# Windows x64 EXE 构建

在 Windows 64 位、Python 3.12 或 3.13 环境中，从仓库根目录执行。
使用项目 `.venv`，不向系统 Python 安装依赖。首次安装需要联网。

```powershell
.\run.bat --setup
.\.venv\Scripts\python.exe -m pip install -r desktop_pet\requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s desktop_pet\tests -v
```

先构建文件夹版，并检查冻结后的资源路径、动画、托盘和完整应用生命周期：

```powershell
.\.venv\Scripts\python.exe scripts\build_windows.py --mode onedir
```

使用 PowerShell 等待 GUI 程序退出并查看自检报告（测试数据不会写入正常用户目录）：

```powershell
$taskRoot = (Get-Location).Path
$taskArgs = '--self-test --data-dir "' + $taskRoot + '\build\qa\onedir-state" --report-file "' + $taskRoot + '\build\qa\onedir-report.json"'
$taskProcess = Start-Process .\dist\onedir\LittleDragonPet\LittleDragonPet.exe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru
$taskProcess.WaitForExit()
Get-Content .\build\qa\onedir-report.json
```

报告需为 `ok: true`、`frozen: true`，各功能检查项均通过。自检会自动退出。
包括学习日历、复盘保存和计时/答题状态汇总；自检题目均为合成数据，仅写入指定测试目录。
随后生成单文件版和完整发行 ZIP：

```powershell
.\.venv\Scripts\python.exe scripts\build_windows.py --mode onefile
```

输出：

- `dist/onefile/LittleDragonPet.exe`：原始单文件程序。
- `dist/LittleDragonPet-Windows-x64/小龙娘.exe`：供用户双击的同一程序。
- `dist/LittleDragonPet-Windows-x64.zip`：程序、使用说明、代码/素材说明、依赖许可证和 pystray 对应 Python 源码。
- `BUILD_INFO.json`：构建版本、程序和动画 SHA-256；不包含开发者绝对路径。

对单文件版也运行上述自检，只需替换 EXE、数据目录和报告文件路径。
动画、默认配置、Tk 与依赖打入程序；个人配置、题单和回执不打包。
正常 EXE 数据目录为 `%LOCALAPPDATA%\LittleDragonDesktopPet\`。

构建会自动检查：模板倒计时默认关闭，没有预设日期、标题或坐标，
EXE 归档中没有个人配置、题单、日历历史或日志，应用字节码不含开发者用户绝对路径。
也可单独执行：

```powershell
.\.venv\Scripts\python.exe scripts\audit_release.py dist\onefile\LittleDragonPet.exe
```

程序目前没有数字签名。单文件模式首次启动需要解包到系统临时目录，可能稍慢；
本地构建和自检不代表所有 Windows 版本或全新虚拟机都已验证。
不要要求用户关闭杀毒软件或使用管理员身份启动。

将源码和构建脚本提交到 Git，将完整发行 ZIP 上传到 GitHub Releases，
不要将 `.venv/`、`build/`、`dist/` 或个人运行数据加入 Git。
发布前按 [发布检查清单](RELEASE_CHECKLIST.md) 核对许可与素材状态。
