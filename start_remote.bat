@echo off
title Hedge Fund Remote Controller
color 0b
chcp 65001 >nul
cls
echo ====================================================
echo       AI HEDGE FUND - REMOTE CONTROL SERVER
echo ====================================================
echo.
echo  [1] Starting Local Control Server...
start "" python remote_controller.py

echo.
echo  [2] Getting Tunnel Password (External IP)...
echo      ...
for /f "delims=" %%a in ('curl -s https://loca.lt/mytunnelpassword') do set "Pass=%%a"

echo.
echo  ====================================================
echo  PASSWORD:  %Pass%
echo  ====================================================
echo.
echo  [3] Starting Secure Tunnel...
echo.
echo  PLEASE WAIT for the URL below. 
echo  It will look like: https://xxxx-xxxx-xxxx.loca.lt
echo.
echo  WHEN ASKED FOR A PASSWORD, ENTER: %Pass%
echo.
echo ====================================================
echo.

call npx localtunnel --port 5000

pause
