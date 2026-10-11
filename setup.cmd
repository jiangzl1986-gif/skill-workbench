@echo off
pushd "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\setup.ps1"
if errorlevel 1 pause
popd
