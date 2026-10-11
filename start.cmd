@echo off
pushd "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\start.ps1"
if errorlevel 1 pause
popd
