@echo off
REM ---------------------------------------------------------------
REM 0.  Globals
REM ---------------------------------------------------------------
setlocal enabledelayedexpansion
set "PROJECT_ROOT=%~dp0"
set "NO_COLOR=1"

REM ---------------------------------------------------------------
REM 1.  Redis  (unchanged)     <‑‑ your existing port‑check block
REM ---------------------------------------------------------------

REM ---------------------------------------------------------------
REM 2.  Back‑end
REM ---------------------------------------------------------------
pushd backend
if not exist venv\Scripts\activate (
    python -m venv venv
)
call venv\Scripts\activate
set "PYTHONPATH=%PROJECT_ROOT%"

REM Celery worker  (Windows needs --pool=solo)
start "" /b "%PROJECT_ROOT%\venv\Scripts\python.exe" ^
        -m celery -A celery_app worker --loglevel=info --pool=solo ^
        > "%PROJECT_ROOT%backend\celery_output.log" 2>&1

REM FastAPI
start "" /b "%PROJECT_ROOT%\venv\Scripts\python.exe" ^
        main.py ^
        > "%PROJECT_ROOT%backend\api_output.log" 2>&1
popd

REM ---------------------------------------------------------------
REM 3.  Front‑end
REM ---------------------------------------------------------------
pushd frontend
chcp 65001 >nul
start "" /b npm run dev > "%PROJECT_ROOT%frontend\frontend_output.log" 2>&1
popd

echo.
echo All services are up.  Logs:
echo   backend\celery_output.log
echo   backend\api_output.log
echo   frontend_output.log
echo.
echo Press Ctrl+C to close THIS window – the background services will
echo also terminate because they share this console.
timeout /t 86400 >nul
