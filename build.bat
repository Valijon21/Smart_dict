@echo off
chcp 65001 >nul
title Vocab Master Pro — Production Build
cd /d "%~dp0"

echo =================================================================
echo  VOCAB MASTER PRO — STANDALONE EXE BUILDER
echo =================================================================
echo.

if exist "venv\Scripts\python.exe" (
    echo [INFO] Virtual muhit (venv) faollashtirilmoqda...
    "venv\Scripts\python.exe" build_exe.py
) else (
    echo [OGOHLANTIRISH] venv topilmadi, tizim Python interpreteridan foydalaniladi...
    python build_exe.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [XATOLIK] Build jarayonida xatolik yuz berdi!
) else (
    echo.
    echo [TABRIKLAYMIZ] Distributiv muvaffaqiyatli tayyorlandi!
)

echo.
echo Oynani yopish uchun istalgan tugmani bosing...
pause >nul
