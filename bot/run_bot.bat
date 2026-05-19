@echo off
chcp 65001 > nul
echo.
echo ====================================
echo   Dooray MCP Bot 시작
echo ====================================
echo.
cd /d "%~dp0\.."
pip install flask anthropic -q 2>nul
echo.
python bot/app.py
pause
