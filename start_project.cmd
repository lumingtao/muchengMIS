@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%LOCALAPPDATA%\Python\bin\python.exe"

if not exist "%PYTHON%" (
  set "PYTHON=python"
)

if "%~1"=="" (
  "%PYTHON%" "%ROOT%project_ctl.py" start
) else (
  "%PYTHON%" "%ROOT%project_ctl.py" %*
)

endlocal
