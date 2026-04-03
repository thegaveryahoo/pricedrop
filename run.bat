@echo off
title PriceDrop Scanner
cd /d "%~dp0"
echo.
echo  ====================================
echo   PriceDrop Scanner - Prijsfout Detector
echo  ====================================
echo.
echo  [1] Webapp starten (dashboard in browser)
echo  [2] Eenmalige scan (alleen terminal)
echo  [3] Continue scan (elke 20 min, terminal)
echo.
set /p choice="Keuze (1, 2 of 3): "

if "%choice%"=="1" (
    python webapp.py
) else if "%choice%"=="2" (
    python scanner.py
    echo.
    pause
) else if "%choice%"=="3" (
    python scanner.py --loop
) else (
    echo Ongeldige keuze.
    pause
)
