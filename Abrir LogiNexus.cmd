@echo off
setlocal
cd /d "%~dp0"
if defined LOGINEXUS_PYTHON goto configured
if exist "%~dp0.venv\Scripts\python.exe" set "LOGINEXUS_PYTHON=%~dp0.venv\Scripts\python.exe"
if defined LOGINEXUS_PYTHON goto configured
if exist "%USERPROFILE%\miniconda3\envs\freight-intelligence\python.exe" set "LOGINEXUS_PYTHON=%USERPROFILE%\miniconda3\envs\freight-intelligence\python.exe"
if defined LOGINEXUS_PYTHON goto configured
echo Ambiente Python do projeto nao encontrado.
echo Configure LOGINEXUS_PYTHON com o caminho do python.exe do projeto.
pause
exit /b 1
:configured
"%LOGINEXUS_PYTHON%" -m freight_intelligence.launch_dashboard
if errorlevel 1 pause
endlocal
