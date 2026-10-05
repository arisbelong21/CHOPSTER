@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0..;%PYTHONPATH%"
set "VERSION=unknown"
if exist "VERSION.txt" set /p VERSION=<"VERSION.txt"
echo ========================================
echo Chopster Dual AI Audit v%VERSION%
echo ========================================
python -m unittest discover -s tests -p "test_*.py" -v
if errorlevel 1 (
  echo.
  echo [FAIL] Dual AI audit gagal.
  pause
  exit /b 1
)
echo.
echo [PASS] Dual AI + Vision + Failover audit selesai.
pause
