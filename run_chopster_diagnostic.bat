@echo off
setlocal
cd /d "%~dp0"
set "QT_LOGGING_RULES=*\.debug=false;qt.multimedia.ffmpeg=false;qt.multimedia.ffmpeg.*=false"
set "QT_FFMPEG_DEBUG=0"
set "QT_MEDIA_BACKEND=ffmpeg"
set "PYTHONUNBUFFERED=1"
echo Chopster diagnostic mode
python main.py > "%~dp0chopster_console.log" 2>&1
set "RC=%errorlevel%"
echo Exit code: %RC%
echo Console log: %~dp0chopster_console.log
pause
endlocal
