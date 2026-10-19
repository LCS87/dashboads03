"""Rastreador Nominal de Recuperação.

Registra e analisa as **ações de cobrança/recuperação por linha** (telefone + mês),
permitindo medir SLA real de primeiro contato, taxa de conversão e produtividade
das equipes de recuperação.

Persistência: arquivo `acoes_recuperacao.csv` (delimitado por `;`, UTF-8 com BOM),
append-only — cada ação é uma linha e o histórico nunca é sobrescrito.

Estrutura do registro de ação:
    ID_ACAO | DT_ACAO | NUMTELEFONE | REFERENCIA | CLIENTE | CANAL |
    RESULTADO | OPERADOR | DT_RETORNO | OBSERVACAO
"""
from __future__ import annotations

import os
from datetime import date

import pandas as pd

from logging_config import get_logger, mascarar

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_ACOES = os.path.join(BASE_DIR, "acoes_recuperacao.csv")

log = get_logger("rastreador")

# ===================== DOMÍNIO =====================

CANAIS = [
    "WhatsApp",
    "Ligação",
    "E-mail",
    "SMS",
    "Visita presencial",
    "Outro",
]

RESULTADOS = [
    "Sem resposta",
    "Contato efetivo",
    "Promessa de pagamento",
    "Recuperado",
    "Recusou / não paga",
    "Número inválido",
]

# Resultados que contam como recuperação efetiva da linha
RESULTADOS_RECUPERADO = {"Recuperado"}

# SLA recomendado de primeiro contato (em dias) por faixa de risco.
# Faixas mais quentes exigem reação mais rápida.
SLA_RECOMENDADO_DIAS: dict[str, int] = {
    "Baixo (Janela de Ouro)": 3,
    "Médio (Atenção)": 2,
    "Alto (Risco Crítico)": 1,
    "Extremo (Pré-Desconexão)": 1,
}

COLUNAS = [
    "ID_ACAO", "DT_ACAO", "NUMTELEFONE", "REFERENCIA", "CLIENTE",
    "CANAL", "RESULTADO", "OPERADOR", "DT_RETORNO", "OBSERVACAO",
]


class AcaoInvalidaError(ValueError):
    """Erro de validação ao registrar uma ação de recuperação."""


# ===================== PERSISTÊNCIA =====================

def _esquema_vazio() -> pd.DataFrame:
    """DataFrame vazio com os tipos corretos (evita avisos de concat com colunas all-NA)."""
    return pd.DataFrame({
        "ID_ACAO": pd.Series(dtype="object"),
        "DT_ACAO": pd.Series(dtype="datetime64[ns]"),
        "NUMTELEFONE": pd.Series(dtype="object"),
        "REFERENCIA": pd.Series(dtype="Int64"),
        "CLIENTE": pd.Series(dtype="object"),
        "CANAL": pd.Series(dtype="object"),
        "RESULTADO": pd.Series(dtype="object"),
        "OPERADOR": pd.Series(dtype="object"),
        "DT_RETORNO": pd.Series(dtype="datetime64[ns]"),
        "OBSERVACAO": pd.Series(dtype="object"),
    })


def carregar_acoes() -> pd.DataFrame:
    """Carrega o histórico de ações. Devolve um DataFrame vazio (com esquema) se não houver arquivo."""
    if not os.path.exists(ARQUIVO_ACOES):
        return _esquema_vazio()

    try:
        acoes = pd.read_csv(ARQUIVO_ACOES, sep=";", encoding="utf-8-sig", dtype={"NUMTELEFONE": str})
    except Exception as erro:
        log.error("Falha ao ler %s: %s", os.path.basename(ARQUIVO_ACOES), erro)
        return _esquema_vazio()

    # Garante o esquema mesmo em arquivos parciais/legados
    for coluna in COLUNAS:
        if coluna not in acoes.columns:
            acoes[coluna] = pd.NA
    acoes = acoes[COLUNAS]

    acoes["DT_ACAO"] = pd.to_datetime(acoes["DT_ACAO"], errors="coerce")
    acoes["DT_RETORNO"] = pd.to_datetime(acoes["DT_RETORNO"], errors="coerce")
    acoes["REFERENCIA"] = pd.to_numeric(acoes["REFERENCIA"], errors="coerce")
    return acoes


def _proximo_id(acoes: pd.DataFrame) -> str:
    """Gera o próximo identificador sequencial de ação (ex.: A00012)."""
    if acoes.empty:
        return "A00001"
    numeros = (
        acoes["ID_ACAO"].astype(str).str.extract(r"(\d+)$")[0]
        .dropna().astype(int)
    )
    proximo = int(numeros.max()) + 1 if len(numeros) else 1
    return f"A{proximo:05d}"


def registrar_acao(
    numtelefone: str | int,
    referencia: int | str,
    canal: str,
    resultado: str,
    operador: str,
    cliente: str = "",
    observacao: str = "",
    dt_retorno: str | date | pd.Timestamp | None = None,
    dt_acao: str | date | pd.Timestamp | None = None,
) -> dict:
    """Valida e persiste uma ação de recuperação (append no CSV).

    Returns:
        dict com o registro gravado (inclui o ID_ACAO gerado).

    Raises:
        AcaoInvalidaError: quando algum campo obrigatório é inválido.
    """
    # --- Validação ---
    tel = str(numtelefone).strip()
    if not tel or tel.lower() in {"nan", "none", "<na>"}:
        raise AcaoInvalidaError("Linha (telefone) é obrigatória.")
    if canal not in CANAIS:
        raise AcaoInvalidaError(f"Canal inválido: '{canal}'. Opções: {CANAIS}.")
    if resultado not in RESULTADOS:
        raise AcaoInvalidaError(f"Resultado inválido: '{resultado}'. Opções: {RESULTADOS}.")
    if not str(operador).strip():
        raise AcaoInvalidaError("Operador é obrigatório (rastreabilidade da ação).")
    try:
        ref = int(referencia)
    except (TypeError, ValueError):
        raise AcaoInvalidaError(f"Referência inválida: {referencia!r} (esperado AAAAmm).")

    registro = {
        "DT_ACAO": pd.to_datetime(dt_acao) if dt_acao is not None else pd.Timestamp.now().floor("s"),
        "NUMTELEFONE": tel,
        "REFERENCIA": ref,
        "CLIENTE": str(cliente).strip(),
        "CANAL": canal,
        "RESULTADO": resultado,
        "OPERADOR": str(operador).strip(),
        "DT_RETORNO": pd.to_datetime(dt_retorno) if dt_retorno is not None else pd.NaT,
        "OBSERVACAO": str(observacao).strip().replace("\n", " "),
    }

    acoes = carregar_acoes()
    registro = {"ID_ACAO": _proximo_id(acoes), **registro}
    acoes = pd.concat([acoes, pd.DataFrame([registro])], ignore_index=True)

    try:
        acoes.to_csv(ARQUIVO_ACOES, sep=";", index=False, encoding="utf-8-sig")
    except Exception as erro:
        log.error("Falha ao gravar ação de recuperação: %s", erro)
        raise

    log.info(
        "Ação registrada %s | linha %s | ref %s | canal=%s | resultado=%s | operador=%s",
        registro["ID_ACAO"], mascarar(tel), ref, canal, resultado, operador,
    )
    return registro


# ===================== MÉTRICAS =====================

def _chave_linha(df: pd.DataFrame) -> pd.Series:
    """Chave de negócio de uma linha suspensa: telefone + mês de referência."""
    return df["NUMTELEFONE"].astype(str) + "|" + df["REFERENCIA"].astype("Int64").astype(str)


def responder(df_acoes: pd.DataFrame, df_base: pd.DataFrame) -> pd.DataFrame:
    """Enriquece as ações com dados da base (faixa de risco, cliente, data de suspensão)."""
    if df_acoes.empty:
        return df_acoes.assign(
            FAIXA_RISCO=pd.Series(dtype="object"),
            DT_SUSPENSAO=pd.Series(dtype="datetime64[ns]"),
            CLIENTE_BASE=pd.Series(dtype="object"),
        )

    base = df_base[["NUMTELEFONE_STR", "REFERENCIA", "FAIXA_RISCO", "DT_SUSPENSAO", "CLIENTE"]].copy()
    base["NUMTELEFONE"] = base["NUMTELEFONE_STR"].astype(str)
    base = base.rename(columns={"CLIENTE": "CLIENTE_BASE"}).drop(columns=["NUMTELEFONE_STR"])
    base = base.drop_duplicates(subset=["NUMTELEFONE", "REFERENCIA"])

    acoes = df_acoes.copy()
    acoes["NUMTELEFONE"] = acoes["NUMTELEFONE"].astype(str)
    acoes["REFERENCIA"] = pd.to_numeric(acoes["REFERENCIA"], errors="coerce")

    return acoes.merge(base, on=["NUMTELEFONE", "REFERENCIA"], how="left")


def resumo_acoes(df_acoes: pd.DataFrame, df_base: pd.DataFrame, ticket_medio: float = 45.0) -> dict:
    """Consolida os KPIs do rastreador de recuperação."""
    vazio = {
        "total_acoes": 0, "linhas_acionadas": 0, "clientes_acionados": 0,
        "linhas_recuperadas": 0, "taxa_conversao": 0.0, "mrr_recuperado": 0.0,
        "tempo_medio_1o_contato": None, "pct_dentro_sla": None, "sla_dias": None,
        "dentro_sla": 0, "com_data_suspensao": 0,
    }
    if df_acoes.empty:
        return vazio

    acoes = responder(df_acoes, df_base)
    acoes["_chave"] = _chave_linha(acoes)

    total_acoes = len(acoes)
    linhas_acionadas = acoes["_chave"].nunique()
    recuperadas = acoes[acoes["RESULTADO"].isin(RESULTADOS_RECUPERADO)]
    linhas_recuperadas = recuperadas["_chave"].nunique()
    clientes_acionados = acoes["CLIENTE_BASE"].fillna(acoes["CLIENTE"]).nunique()

    # SLA: tempo entre a suspensão (base) e o primeiro contato registrado
    primeira_acao = (
        acoes.dropna(subset=["DT_SUSPENSAO"])
        .sort_values("DT_ACAO")
        .groupby("_chave", as_index=False)
        .first()
    )
    tempo_medio = None
    pct_dentro_sla = None
    dentro_sla = 0
    com_data = len(primeira_acao)
    if com_data:
        primeira_acao = primeira_acao.copy()
        primeira_acao["DIAS_ATE_CONTATO"] = (
            primeira_acao["DT_ACAO"].dt.normalize() - primeira_acao["DT_SUSPENSAO"].dt.normalize()
        ).dt.days.clip(lower=0)
        tempo_medio = float(primeira_acao["DIAS_ATE_CONTATO"].mean())
        sla_por_linha = primeira_acao["FAIXA_RISCO"].map(SLA_RECOMENDADO_DIAS).fillna(
            SLA_RECOMENDADO_DIAS["Baixo (Janela de Ouro)"]
        )
        dentro_sla = int((primeira_acao["DIAS_ATE_CONTATO"] <= sla_por_linha).sum())
        pct_dentro_sla = dentro_sla / com_data * 100

    return {
        "total_acoes": total_acoes,
        "linhas_acionadas": linhas_acionadas,
        "clientes_acionados": clientes_acionados,
        "linhas_recuperadas": linhas_recuperadas,
        "taxa_conversao": (linhas_recuperadas / linhas_acionadas * 100) if linhas_acionadas else 0.0,
        "mrr_recuperado": linhas_recuperadas * ticket_medio,
        "tempo_medio_1o_contato": tempo_medio,
        "pct_dentro_sla": pct_dentro_sla,
        "sla_dias": SLA_RECOMENDADO_DIAS,
        "dentro_sla": dentro_sla,
        "com_data_suspensao": com_data,
    }


def sla_por_faixa(df_acoes: pd.DataFrame, df_base: pd.DataFrame) -> pd.DataFrame:
    """Tabela de SLA por faixa de risco: linhas acionadas, tempo médio e aderência."""
    colunas = ["FAIXA_RISCO", "SLA_ALVO_DIAS", "LINHAS_ACIONADAS", "TEMPO_MEDIO", "DENTRO_SLA", "ADERENCIA_%"]
    if df_acoes.empty:
        return pd.DataFrame(columns=colunas)

    acoes = responder(df_acoes, df_base)
    acoes["_chave"] = _chave_linha(acoes)
    acoes = acoes.dropna(subset=["DT_SUSPENSAO", "FAIXA_RISCO"])
    if acoes.empty:
        return pd.DataFrame(columns=colunas)

    primeira = acoes.sort_values("DT_ACAO").groupby("_chave", as_index=False).first()
    primeira["DIAS_ATE_CONTATO"] = (
        primeira["DT_ACAO"].dt.normalize() - primeira["DT_SUSPENSAO"].dt.normalize()
    ).dt.days.clip(lower=0)
    primeira["SLA_ALVO_DIAS"] = primeira["FAIXA_RISCO"].map(SLA_RECOMENDADO_DIAS).fillna(3).astype(int)
    primeira["DENTRO"] = primeira["DIAS_ATE_CONTATO"] <= primeira["SLA_ALVO_DIAS"]

    tabela = primeira.groupby(["FAIXA_RISCO", "SLA_ALVO_DIAS"]).agg(
        LINHAS_ACIONADAS=("_chave", "nunique"),
        TEMPO_MEDIO=("DIAS_ATE_CONTATO", "mean"),
        DENTRO_SLA=("DENTRO", "sum"),
    ).reset_index()
    tabela["ADERENCIA_%"] = (tabela["DENTRO_SLA"] / tabela["LINHAS_ACIONADAS"] * 100).round(1)
    tabela["TEMPO_MEDIO"] = tabela["TEMPO_MEDIO"].round(1)
    ordem = {faixa: i for i, faixa in enumerate(SLA_RECOMENDADO_DIAS)}
    tabela["_ordem"] = tabela["FAIXA_RISCO"].map(ordem).fillna(99)
    return tabela.sort_values("_ordem").drop(columns="_ordem")[colunas].reset_index(drop=True)


def recuperacao_observada(df_base: pd.DataFrame) -> pd.DataFrame:
    """Indicador indireto: linhas ativas em um mês e ausentes no mês seguinte.

    Interpretação: a linha saiu do parque suspenso — tipicamente por **reativação
    (pagamento)** ou por cancelamento definitivo. Serve como sinal objetivo de
    recuperação quando não há registro manual da ação.
    """
    colunas = ["REFERENCIA_LABEL", "LINHAS", "SAIRAM", "PERMANECERAM", "TAXA_SAIDA_%"]
    if df_base.empty or df_base["REFERENCIA"].nunique() < 2:
        return pd.DataFrame(columns=colunas)

    meses = (
        df_base[["REFERENCIA", "REFERENCIA_LABEL"]].drop_duplicates()
        .sort_values("REFERENCIA")
    )
    linhas_por_mes = {
        ref: set(df_base.loc[df_base["REFERENCIA"] == ref, "NUMTELEFONE_STR"].astype(str))
        for ref in meses["REFERENCIA"]
    }

    registros = []
    refs = list(meses["REFERENCIA"])
    for i, ref in enumerate(refs[:-1]):
        atual = linhas_por_mes[ref]
        proximo = linhas_por_mes[refs[i + 1]]
        if not atual:
            continue
        sairam = len(atual - proximo)
        registros.append({
            "REFERENCIA_LABEL": meses.loc[meses["REFERENCIA"] == ref, "REFERENCIA_LABEL"].iloc[0],
            "LINHAS": len(atual),
            "SAIRAM": sairam,
            "PERMANECERAM": len(atual & proximo),
            "TAXA_SAIDA_%": round(sairam / len(atual) * 100, 1),
        })
    return pd.DataFrame(registros, columns=colunas)


def acoes_por_semana(df_acoes: pd.DataFrame) -> pd.DataFrame:
    """Volume de ações por semana (para o gráfico de evolução)."""
    if df_acoes.empty:
        return pd.DataFrame(columns=["SEMANA", "ACOES"])
    acoes = df_acoes.dropna(subset=["DT_ACAO"]).copy()
    if acoes.empty:
        return pd.DataFrame(columns=["SEMANA", "ACOES"])
    acoes["SEMANA"] = acoes["DT_ACAO"].dt.to_period("W").dt.start_time
    return (
        acoes.groupby("SEMANA").size().reset_index(name="ACOES")
        .sort_values("SEMANA")
    )


def acoes_por(df_acoes: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Contagem de ações por uma dimensão (CANAL, RESULTADO, OPERADOR)."""
    if df_acoes.empty or coluna not in df_acoes.columns:
        return pd.DataFrame(columns=[coluna, "ACOES"])
    return (
        df_acoes[coluna].fillna("N/I").value_counts()
        .rename_axis(coluna).reset_index(name="ACOES")
    )
