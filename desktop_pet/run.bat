@echo off
setlocal
cd /d "%~dp0"
py -3.13 -c "import sys" >nul 2>&1
if errorlevel 1 goto try_python312
py -3.13 bootstrap.py %*
goto finished

:try_python312
py -3.12 -c "import sys" >nul 2>&1
if errorlevel 1 goto try_path
py -3.12 bootstrap.py %*
goto finished

:try_path
for /f "delims=" %%P in ('where python 2^>nul') do (
    if /i not "%%~dpP"=="%LOCALAPPDATA%\Microsoft\WindowsApps\" (
        "%%P" -c "import sys; assert (3,12) <= sys.version_info[:2] < (3,14)" >nul 2>&1
        if not errorlevel 1 (
            "%%P" bootstrap.py %*
            goto finished
        )
    )
)
echo This source edition requires Python 3.12 or 3.13 with Tcl/Tk.
echo Install Python from https://www.python.org/downloads/windows/ and retry.
pause
exit /b 1

:finished
if errorlevel 1 (
    echo Setup/startup failed. See the error above and README.md.
    pause
    exit /b 1
)
exit /b 0
