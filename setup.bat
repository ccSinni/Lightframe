@echo off
setlocal

echo ============================================
echo  LightFrame - Setup
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Download from https://python.org
    pause & exit /b 1
)

echo [1/3] Installing Python packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed. Check your Python/pip setup.
    pause & exit /b 1
)
echo    Done.
echo.

:: Check for mpv-2.dll
if not exist "mpv-2.dll" (
    echo [2/3] mpv-2.dll NOT FOUND in this folder.
    echo.
    echo      You must download the MPV Windows build manually:
    echo        1. Go to  https://mpv.io/installation/
    echo        2. Click "Windows builds by shinchiro" (or similar)
    echo        3. Download the latest 64-bit 7z archive
    echo        4. Extract it - inside you will find  libmpv-2.dll
    echo        5. Rename it to  mpv-2.dll
    echo        6. Copy  mpv-2.dll  into this folder
    echo.
) else (
    echo [2/3] mpv-2.dll found. OK.
)

:: Check FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [3/3] FFmpeg NOT found in PATH.
    echo.
    echo      For Trim/Export to work you need FFmpeg:
    echo        1. Go to  https://ffmpeg.org/download.html
    echo        2. Download a Windows build (e.g. from gyan.dev)
    echo        3. Extract and add the  bin\  folder to your system PATH
    echo.
) else (
    echo [3/3] FFmpeg found. OK.
)

echo.
echo ============================================
echo  Run the player with:   python main.py
echo ============================================
pause
