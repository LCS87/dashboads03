@echo off
title Dashboard Executivo - Parque Suspenso
setlocal enabledelayedexpansion

echo ========================================================
echo   INICIANDO COCKPIT EXECUTIVO - PARQUE SUSPENSO
echo   PAINEL EXECUTIVO - GESTAO DE PARQUE SUSPENSO
echo ========================================================
echo.

REM ================= PORTA =================
REM Uso: iniciar_dashboard.bat [8503 | service]
set "PORT=8503"
if not "%~1"=="" if not "%~1"=="service" set "PORT=%~1"

call :liberar_porta "%PORT%"
if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel liberar a porta %PORT%.
    echo     Feche o processo que a ocupa e execute novamente,
    echo     ou use outra porta:  iniciar_dashboard.bat 8600
    pause
    exit /b 1
)
echo.

REM ================= DEPENDENCIAS =================
echo Verificando dependencias...
python -c "import streamlit, pandas, plotly, pyarrow" 2>nul
if errorlevel 1 (
    echo Instalando dependencias do requirements.txt...
    python -m pip install -r requirements.txt
)
python -c "import reportlab" 2>nul
if errorlevel 1 (
    echo Instalando reportlab (exportacao de PDF)...
    python -m pip install reportlab --quiet
)
echo.

REM ================= DADOS TRATADOS =================
echo Verificando se os dados tratados existem...
if not exist "parque_suspenso_tratado.parquet" (
    echo Executando pipeline de tratamento e enriquecimento de dados...
    python etl_pipeline.py
) else (
    echo Detectando novos arquivos mensais e atualizando a base...
    python -c "from etl_pipeline import refresh_if_new_months; refresh_if_new_months()"
)
echo.

REM ================= SUBIDA =================
echo Modo de execucao: %1
if "%1"=="service" (
    echo Iniciando como servico Windows...
    echo Use o Gerenciador de Servicos (services.msc) ou:
    echo   net start parque-suspenso
    python -m streamlit run app.py --server.port %PORT% --server.headless true --server.runnerType=edgece
) else (
    echo Iniciando aplicacao Streamlit na porta %PORT%...
    echo   http://localhost:%PORT%
    echo.
    echo Use o parametro "service" para iniciar como servico Windows.
    echo Para usar outra porta:  iniciar_dashboard.bat 8600
    echo.
    python -m streamlit run app.py --server.port %PORT%
)
pause
exit /b 0

REM ================= SUBROTINA =================
:liberar_porta
set "P=%~1"
set "PIDS="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%P%" ^| findstr "LISTENING"') do (
    if not "%%p"=="0" set "PIDS=!PIDS! %%p"
)
if not defined PIDS goto :porta_livre
echo [ATENCAO] Porta !P! ja em uso por PID:!PIDS!
echo     Encerrando a instancia anterior do dashboard...
for %%p in (!PIDS!) do powershell -NoProfile -Command "Stop-Process -Id %%p -Force -ErrorAction SilentlyContinue"
for /l %%i in (1,1,10) do (
    ping -n 2 127.0.0.1 >nul
    set "AINDA="
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%P%" ^| findstr "LISTENING"') do (
        if not "%%p"=="0" set "AINDA=1"
    )
    if not defined AINDA goto :porta_livre
)
echo [ERRO] O processo que ocupa a porta !P! nao encerrou.
exit /b 1
:porta_livre
echo [OK] Porta !P! livre.
exit /b 0
