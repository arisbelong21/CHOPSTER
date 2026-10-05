@echo off
setlocal
REM Regression for the Camera Director / Master Analysis path (dependency-light).
cd /d "%~dp0.."
set PYTHONPATH=.
python -m unittest discover -s chopster\tests -p "test_*.py" -v
if errorlevel 1 (
  echo [FAIL] Camera AI pipeline regression test failed.
  pause
  exit /b 1
)
echo [OK] Camera AI pipeline tests passed.
pause
