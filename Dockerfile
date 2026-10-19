# ============================================================
#  Cockpit Executivo — Parque Suspenso
#  Estágios:
#    base    → dependências de runtime + código + usuário não-root
#    runtime → imagem de produção (padrão do docker compose)
#    test    → base + pytest (para CI / `docker compose run testes`)
# ============================================================

# ------------------------------------------------------------
FROM python:3.11-slim AS base

LABEL org.opencontainers.image.title="Cockpit Executivo — Parque Suspenso" \
      org.opencontainers.image.description="Dashboard executivo de gestão de linhas corporativas suspensas"

# --- Ambiente Python enxuto e previsível ---
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Sao_Paulo \
    STREAMLIT_SERVER_PORT=8503 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# --- Dependências primeiro (aproveita o cache de camadas) ---
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- Entrypoint fora de /app (sobrevive a bind mounts) ---
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

# --- Código e dados ---
COPY . .

# --- Usuário não-root ---
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app


# ------------------------------------------------------------
#  runtime — imagem de produção
# ------------------------------------------------------------
FROM base AS runtime

USER appuser
WORKDIR /app
EXPOSE 8503

# --- Saúde do serviço: endpoint nativo do Streamlit ---
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8503/_stcore/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["streamlit", "run", "app.py", \
     "--server.port=8503", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]


# ------------------------------------------------------------
#  test — base + pytest (CI local ou `docker compose run --rm testes`)
# ------------------------------------------------------------
FROM base AS test

USER root
RUN pip install --no-cache-dir pytest

USER appuser
WORKDIR /app
ENTRYPOINT []
CMD ["python", "-m", "pytest", "-q", "-m", "not ui"]
