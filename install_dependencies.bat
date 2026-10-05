@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "VERSION=unknown"
if exist "VERSION.txt" set /p VERSION=<"VERSION.txt"
echo ========================================
echo   Chopster by Aris v%VERSION% - Install
echo ========================================
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

REM yt-dlp[default] installs a matching yt-dlp-ejs package. Do not upgrade
REM yt-dlp-ejs independently because the EJS version must match yt-dlp.
python -c "import yt_dlp,yt_dlp_ejs; print('yt-dlp OK:', yt_dlp.version.__version__)"
if errorlevel 1 goto :fail

echo.
echo Checking YouTube JavaScript runtime...
set "DENO_LOCAL=%~dp0deno.exe"
if exist "%DENO_LOCAL%" goto :validate_deno_local
for /f "delims=" %%D in ('where deno 2^>nul') do if not defined DENO_LOCAL set "DENO_LOCAL=%%D"
if defined DENO_LOCAL goto :validate_deno_local

REM Try WinGet first (user scope, no admin prompt in normal cases).
where winget >nul 2>&1
if not errorlevel 1 (
  echo [INFO] Deno belum ada. Mencoba memasang Deno via WinGet...
  winget install --id=DenoLand.Deno --scope user --accept-source-agreements --accept-package-agreements
  for /f "delims=" %%D in ('where deno 2^>nul') do if not defined DENO_LOCAL set "DENO_LOCAL=%%D"
  if not defined DENO_LOCAL if exist "%USERPROFILE%\.deno\bin\deno.exe" set "DENO_LOCAL=%USERPROFILE%\.deno\bin\deno.exe"
  if defined DENO_LOCAL goto :validate_deno_local
)

REM Fallback: official Deno installer. It installs per-user.
echo [INFO] Mencoba installer resmi Deno...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://deno.land/install.ps1 | iex"
if exist "%USERPROFILE%\.deno\bin\deno.exe" set "DENO_LOCAL=%USERPROFILE%\.deno\bin\deno.exe"
if defined DENO_LOCAL goto :validate_deno_local

where node >nul 2>&1
if not errorlevel 1 goto :node_ok

echo [WARN] Deno/Node belum tersedia.
echo        YouTube modern membutuhkan Deno ^>=2.3 atau Node ^>=22.
echo        Coba jalankan lagi installer ini setelah internet/WinGet tersedia.
goto :done

:validate_deno_local
"%DENO_LOCAL%" --version >nul 2>&1
if errorlevel 1 (
  echo [WARN] Deno ditemukan tetapi gagal dijalankan, akan diabaikan: %DENO_LOCAL%
  set "DENO_LOCAL="
  where node >nul 2>&1
  if not errorlevel 1 (
    echo [INFO] Memakai Node sebagai pengganti Deno.
    goto :node_ok
  )
  goto :done
)
echo [OK] Deno siap: %DENO_LOCAL%
"%DENO_LOCAL%" --version
set "PATH=%~dp0;%PATH%"
goto :done

:node_ok
echo [OK] Node ditemukan di PATH.
node --version

:done
echo.
echo [OK] Dependency selesai.
echo Jalankan run_chopster.bat untuk membuka aplikasi.
pause
endlocal
exit /b 0

:fail
echo.
echo [ERROR] Instalasi dependency gagal.
pause
endlocal
exit /b 1
