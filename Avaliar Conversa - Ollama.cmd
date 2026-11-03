@echo off
setlocal
chcp 65001 >nul
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "PYTHON=%PROJECT_DIR%.venv-desktop\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERRO: Ambiente Python .venv-desktop nao encontrado.
  pause
  exit /b 1
)
"%PYTHON%" -c "import streamlit,pypdf" >nul 2>&1
if errorlevel 1 (
  echo ERRO: Dependencias do projeto ausentes em .venv-desktop. Consulte o README.
  pause
  exit /b 1
)
set "OLLAMA_MODEL=qwen3:4b-instruct"
"%PYTHON%" "%PROJECT_DIR%scripts\evaluate_conversations.py" --output "%PROJECT_DIR%conversation-eval-report.json"
if errorlevel 1 echo A avaliacao nao terminou; veja a causa acima.
pause
endlocal
