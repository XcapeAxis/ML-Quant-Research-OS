@echo off
setlocal
set "BT_PLATFORM_MODE=shared"
if "%BT_PLATFORM_HOST%"=="" set "BT_PLATFORM_HOST=0.0.0.0"
if "%BT_PLATFORM_PORT%"=="" set "BT_PLATFORM_PORT=8000"
if "%BT_PLATFORM_MAX_CONCURRENT_JOBS%"=="" set "BT_PLATFORM_MAX_CONCURRENT_JOBS=2"
if "%BT_PLATFORM_PROXY_URL%"=="" set "BT_PLATFORM_PROXY_URL="
if "%BT_PLATFORM_CA_BUNDLE_PATH%"=="" set "BT_PLATFORM_CA_BUNDLE_PATH="
if "%BT_PLATFORM_CONNECT_TIMEOUT_SECONDS%"=="" set "BT_PLATFORM_CONNECT_TIMEOUT_SECONDS=5"
if "%BT_PLATFORM_READ_TIMEOUT_SECONDS%"=="" set "BT_PLATFORM_READ_TIMEOUT_SECONDS=15"
set "API_EXE=%~dp0dist\backtest-platform-api\backtest-platform-api.exe"
set "PYTHON_CMD=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
if exist "%API_EXE%" (
  "%API_EXE%"
) else (
  "%PYTHON_CMD%" -m uvicorn apps.api.main:app --host %BT_PLATFORM_HOST% --port %BT_PLATFORM_PORT%
)
