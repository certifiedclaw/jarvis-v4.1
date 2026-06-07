@echo off
title JARVIS v3 — Setup
color 0B
echo.
echo  ======================================
echo    J A R V I S  v3  —  Setup
echo  ======================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo  Download from https://www.python.org/downloads/
    pause & exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% found

:: Create venv
if not exist .venv (
    echo  Creating virtual environment...
    python -m venv .venv
)
echo  [OK] Virtual environment ready

:: Activate and install
echo  Installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

if errorlevel 1 (
    echo.
    echo  [ERROR] Dependency installation failed.
    echo  Check your internet connection and try again.
    pause & exit /b 1
)

:: Create dirs
if not exist data     mkdir data
if not exist logs     mkdir logs
if not exist plugins  mkdir plugins

:: Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [NOTICE] Ollama not found.
    echo  Download from https://ollama.com/download
    echo  Then run:  ollama pull qwen3:8b
) else (
    echo  [OK] Ollama found
    echo  Pulling default model ^(qwen3:8b^)...
    ollama pull qwen3:8b
)

echo.
echo  ======================================
echo    Setup complete!
echo  ======================================
echo.
echo  To run JARVIS:
echo    .venv\Scripts\python.exe main.py
echo.
echo  Or double-click  run.bat
echo.

:: Create run.bat shortcut
echo @echo off > run.bat
echo cd /d %%~dp0 >> run.bat
echo .venv\Scripts\python.exe main.py %%* >> run.bat

pause
