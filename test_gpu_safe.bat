@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0..;%PYTHONPATH%"
echo ========================================
echo Chopster - Safe GPU Diagnostic
echo ========================================
python -c "from chopster.clipper.transcript_manager import _cuda_preflight; ok,detail=_cuda_preflight(); print(('OK: ' if ok else 'NOT SAFE: ')+detail); raise SystemExit(0 if ok else 1)"
if errorlevel 1 (
  echo.
  echo GPU tidak akan dipakai oleh Device=Auto. Chopster akan memakai CPU.
) else (
  echo.
  echo GPU runtime aman untuk dicoba oleh Device=Auto.
)
pause
endlocal
