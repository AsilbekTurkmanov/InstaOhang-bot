@echo off
title InstaOhang Telegram Bot Launcher
cd /d "%~dp0"

echo ===================================================
echo             InstaOhang Telegram Bot
echo ===================================================
echo.

IF EXIST bin\python\python.exe (
    SET PYTHON_CMD=bin\python\python.exe
) ELSE (
    SET PYTHON_CMD=python
)

echo Using Python from: %PYTHON_CMD%
echo.

:loop
echo [%date% %time%] Bot ishga tushirilmoqda...
%PYTHON_CMD% bot.py
echo.
echo [%date% %time%] Bot to'xtadi yoki qayta yuklanmoqda... 5 soniyadan so'ng qayta yonadi.
timeout /t 5
goto loop
