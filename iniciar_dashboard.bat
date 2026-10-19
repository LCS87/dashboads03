@echo off
title Dashboard Executivo - Parque Suspenso
echo ========================================================
echo   INICIANDO COCKPIT EXECUTIVO - PARQUE SUSPENSO
echo   PAINEL EXECUTIVO - GESTAO DE PARQUE SUSPENSO
echo ========================================================
echo.

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

echo Verificando se os dados tratados existem...
if not exist "parque_suspenso_tratado.parquet" (
    echo Executando pipeline de tratamento e enriquecimento de dados...
    python etl_pipeline.py
) else (
    echo Detectando novos arquivos mensais e atualizando a base...
    python -c "from etl_pipeline import refresh_if_new_months; refresh_if_new_months()"
)
echo.

echo Iniciando aplicacao Streamlit...
python -m streamlit run app.py --server.port 8503
pause
