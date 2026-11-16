@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0air_quality_web"

REM Locate Python interpreter (prefer known path, fall back to PATH)
set "PY="
if exist "D:\Python\Python311\python.exe" set "PY=D:\Python\Python311\python.exe"
if not defined PY (
  for /f "delims=" %%i in ('where python 2^>nul') do ( if not defined PY set "PY=%%i" )
)
if not defined PY (
  echo ERROR: Python not found. Install Python 3 or fix the path in this script.
  pause
  exit /b 1
)
echo Using Python: %PY%

REM Kill any previously started preview servers (serve.py) so they don't pile up
echo Stopping any previous preview servers...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='python.exe' and commandline like '%%serve.py%%'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul
timeout /t 2 >nul

REM Candidate ports: prefer 8765, then spread-out high ports unlikely to collide
set PORTS=8765 18865 28865 38865 48865 58865 68865 78865 88865
set CHOSEN=
for %%P in (%PORTS%) do (
  if not defined CHOSEN (
    netstat -ano 2>nul | findstr /r ":%%P[ ]" >nul
    if !errorlevel!==0 (
      set CHOSEN=%%P
    )
  )
)
if not defined CHOSEN (
  echo ERROR: No free port available.
  pause
  exit /b 1
)

set PORT=%CHOSEN%
echo Starting local server on port %PORT% ...
start /b "" "%PY%" serve.py %PORT%

REM Wait until the server actually answers (poll up to 15 seconds)
set READY=0
for /L %%i in (1,1,15) do (
  powershell -NoProfile -Command "try{(Invoke-WebRequest -Uri 'http://localhost:%PORT%/index.html' -UseBasicParsing -TimeoutSec 1).StatusCode}catch{0}" 2>nul | findstr "200" >nul
  if !errorlevel!==0 (
    set READY=1
    goto :open
  )
  timeout /t 1 >nul
)
:open
if %READY%==1 (
  echo Server is up. Opening browser...
  start "" http://localhost:%PORT%/
) else (
  echo Server did not respond within 15s.
  echo Check the messages above for python/serve.py errors.
  echo If Windows Firewall prompted, allow python through Private networks.
)
echo.
echo Local address: http://localhost:%PORT%/
echo Server is running in this window. Close this window to stop the server.
pause
endlocal
