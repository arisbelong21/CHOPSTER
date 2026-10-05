@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0..;%PYTHONPATH%"
echo ========================================
echo   Chopster - Embedded Gemini Vision Test
echo ========================================
python -c "from chopster.ai.embedded_gemini import EmbeddedGeminiProvider; p=EmbeddedGeminiProvider(timeout=25); print('AVAILABLE:', p.is_available()); print('MODEL:', p.embedded_model)"
if errorlevel 1 echo [ERROR] Embedded Gemini test bootstrap gagal.
pause
