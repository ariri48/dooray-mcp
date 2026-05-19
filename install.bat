@echo off
chcp 65001 > nul
echo.
echo ====================================
echo   Dooray MCP - 설치
echo ====================================
echo.
cd /d "%~dp0"
python setup.py
echo.
pause
