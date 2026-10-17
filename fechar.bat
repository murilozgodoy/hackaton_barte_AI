@echo off
rem Fecha o mes com um comando (Windows; nao testado em Windows pelo time, ver README):
rem   fechar.bat [zip ou pasta com os arquivos do mes] [pasta de saida, padrao: saida] [--anterior <saida do mes anterior>]
rem Cria o ambiente virtual se nao existir, instala as dependencias fixas de requirements.txt,
rem roda "validar" (para com codigo 1 ou 2 se entrada ou regras tiverem problema) e "fechar".
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "ENTRADA=%~1"
set "SAIDA=%~2"
set "ANTERIOR="
if /i "%~2"=="--anterior" (
  set "SAIDA=saida"
  set "ANTERIOR=%~3"
) else if /i "%~3"=="--anterior" (
  set "ANTERIOR=%~4"
)
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
set "ARG_ANTERIOR="
if not "%ANTERIOR%"=="" set ARG_ANTERIOR=--anterior "%ANTERIOR%"
.venv\Scripts\python.exe -m src validar %ARG_ENTRADA% --regras regras
if errorlevel 1 exit /b %errorlevel%
.venv\Scripts\python.exe -m src fechar %ARG_ENTRADA% --regras regras --saida "%SAIDA%" %ARG_ANTERIOR%
exit /b %errorlevel%
