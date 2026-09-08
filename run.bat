@echo off
title Vocab Master
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    start "" "venv\Scripts\python.exe" main.py
) else (
    echo [XATOLIK] Virtual muhit (venv) topilmadi!
    echo Iltimos, avval muhitni yarating: python -m venv venv
    pause
)
