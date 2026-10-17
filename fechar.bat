@echo off
rem Fecha o mes com um comando (Windows):
rem   fechar.bat [zip ou pasta com os arquivos do mes] [pasta de saida, padrao: saida]
rem Cria o ambiente virtual se nao existir, instala as dependencias fixas de requirements.txt,
rem roda "validar" (para com codigo 1 ou 2 se entrada ou regras tiverem problema) e "fechar".
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "ENTRADA=%~1"
set "SAIDA=%~2"
if "%SAIDA%"=="" set "SAIDA=saida"

if exist ".venv\Scripts\python.exe" goto deps
echo Criando o ambiente virtual .venv...
py -3 -m venv .venv 2>nul
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo ERRO: nao encontrei Python 3.10 ou mais novo. Instale em https://www.python.org/downloads/ e rode de novo.
  exit /b 1
)

:deps
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if errorlevel 1 exit /b 1

set "ARG_ENTRADA="
if not "%ENTRADA%"=="" set ARG_ENTRADA=--entrada "%ENTRADA%"
.venv\Scripts\python.exe -m src validar %ARG_ENTRADA% --regras regras
if errorlevel 1 exit /b %errorlevel%
.venv\Scripts\python.exe -m src fechar %ARG_ENTRADA% --regras regras --saida "%SAIDA%"
exit /b %errorlevel%
