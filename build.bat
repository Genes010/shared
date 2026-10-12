@echo off
rem Dubbelklik om SMBConnect.exe te bouwen.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
pause
