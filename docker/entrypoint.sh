#!/usr/bin/env sh
# ============================================================
#  Bootstrap do contêiner: garante a base tratada e sobe o app.
#  Mantido idempotente — pode rodar em todo restart sem efeito colateral.
# ============================================================
set -e

cd /app

if [ ! -f "parque_suspenso_tratado.parquet" ]; then
    echo "[entrypoint] Base tratada ausente — executando o ETL..."
    python etl_pipeline.py || echo "[entrypoint] ETL falhou; o dashboard tentará se recuperar na inicialização."
else
    echo "[entrypoint] Base tratada encontrada. Verificando novos meses..."
    python -c "from etl_pipeline import refresh_if_new_months; refresh_if_new_months()" \
        || echo "[entrypoint] Verificação de novos meses falhou (seguindo com a base atual)."
fi

echo "[entrypoint] Iniciando: $*"
exec "$@"
