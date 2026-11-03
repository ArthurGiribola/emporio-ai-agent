@echo off
setlocal
chcp 65001 >nul
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "PYTHON=%PROJECT_DIR%.venv-desktop\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo ERRO: Ambiente Python .venv-desktop nao encontrado.
  echo Configure o ambiente desktop Python 3.12 conforme o README.
  pause
  exit /b 1
)
"%PYTHON%" -c "import sys,streamlit,webview; assert sys.version_info[:2] == (3,12)" >nul 2>&1
if errorlevel 1 (
  echo ERRO: Dependencias desktop ausentes ou Python diferente de 3.12 em .venv-desktop.
  echo Instale as dependencias uma vez conforme o README. Verifique tambem o WebView2 Runtime.
  pause
  exit /b 1
)
set "EMPORIO_DATA_MODE=local"
set "OLLAMA_MODEL=qwen3:4b-instruct"
set "EMPORIO_ENABLE_DEMO_IDENTITY=0"
set "EMPORIO_ORDER_ID=1"
if not exist "%PROJECT_DIR%data\products.csv" (
  echo ERRO: Arquivos locais nao encontrados em data\. Confira a pasta e a configuracao no README.
  pause
  exit /b 1
)
"%PYTHON%" -m app.desktop
if errorlevel 1 (
  echo O aplicativo nao iniciou. Verifique se o Ollama esta aberto e o modelo qwen3:4b-instruct foi baixado.
  pause
)
endlocal
