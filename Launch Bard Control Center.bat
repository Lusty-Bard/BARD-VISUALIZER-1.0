@echo off
setlocal
python "%~dp0bard_control_launcher.py"
if errorlevel 1 py "%~dp0bard_control_launcher.py"
endlocal
