"""Agregações cacheadas e utilitários de qualidade de dados do dashboard.

Objetivo (Fase 2 do plano de melhorias):
- Evitar recomputar as mesmas agregações em abas/reruns diferentes (cache granular).
- Centralizar regras de negócio (ordenação de faixas, aging, financeiro).
- Expor diagnóstico de qualidade (ex.: duplicatas do pico de Abril).
- Cachear a geração do PDF para não reconstruí-lo a cada interação.
"""
import pandas as pd
import streamlit as st

ORDEM_AGING = [
    "Até 30 dias", "De 31 a 60 dias", "De 61 a 90 dias",
    "De 91 a 120 dias", "Maior que 120 dias", "Não Informado",
]

ORDEM_FAIXA_RISCO = [
    "Baixo (Janela de Ouro)", "Médio (Atenção)",
    "Alto (Risco Crítico)", "Extremo (Pré-Desconexão)",
]

AGING_CRITICO = ["De 61 a 90 dias", "De 91 a 120 dias", "Maior que 120 dias"]


# ===================== QUALIDADE DE DADOS =====================

@st.cache_data(show_spinner=False)
def resumo_qualidade(df: pd.DataFrame) -> dict:
    """Resume a qualidade da base: duplicatas exatas e volume bruto x único por mês."""
    if df.empty:
        return {"duplicatas_exatas": 0, "por_mes": pd.DataFrame()}

    duplicatas = int(df.duplicated().sum())

    por_mes = (
        df.groupby("REFERENCIA_LABEL")
        .agg(BRUTO=("NUMTELEFONE", "count"), UNICOS=("NUMTELEFONE", "nunique"))
        .reset_index()
    )
    por_mes["DUPLICADAS"] = por_mes["BRUTO"] - por_mes["UNICOS"]
    por_mes["FATOR"] = (por_mes["BRUTO"] / por_mes["UNICOS"].replace(0, 1)).round(2)
    return {"duplicatas_exatas": duplicatas, "por_mes": por_mes}


# ===================== AGREGAÇÕES CACHEADAS =====================

@st.cache_data(show_spinner=False)
def resumo_kpis(df: pd.DataFrame) -> dict:
    """KPIs macro do recorte atual."""
    total = len(df)
    if total == 0:
        return {"total_linhas": 0, "total_clientes": 0, "total_inadimp": 0,
                "pct_inadimp": 0.0, "linhas_criticas": 0, "pct_critico": 0.0,
                "tempo_medio": 0.0}
    total_inadimp = int((df["STATUS"] == "INADIMPLENTE").sum())
    criticas = int(df["AGING_LIMPO"].isin(AGING_CRITICO).sum())
    return {
        "total_linhas": total,
        "total_clientes": int(df["CLIENTE"].nunique()),
        "total_inadimp": total_inadimp,
        "pct_inadimp": total_inadimp / total * 100,
        "linhas_criticas": criticas,
        "pct_critico": criticas / total * 100,
        "tempo_medio": float(df["TEMPO_SUSPENSAO"].mean()),
    }


@st.cache_data(show_spinner=False)
def contagens(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """value_counts de uma coluna, já como DataFrame (coluna, CONTAGEM)."""
    serie = df[coluna].value_counts().reset_index()
    serie.columns = [coluna, "CONTAGEM"]
    return serie


@st.cache_data(show_spinner=False)
def historico_mensal(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Volume por mês e status, com ordem cronológica (suporta novos meses)."""
    hist = df_raw.groupby(["REFERENCIA_LABEL", "STATUS"])["NUMTELEFONE"].count().reset_index(name="CONTAGEM")
    ordem = (
        df_raw[["REFERENCIA", "REFERENCIA_LABEL"]].drop_duplicates()
        .sort_values("REFERENCIA")
    )
    mapa = dict(zip(ordem["REFERENCIA_LABEL"], ordem["REFERENCIA"]))
    hist["ORDEM"] = hist["REFERENCIA_LABEL"].map(mapa)
    hist = hist[hist["ORDEM"].notna()].copy()
    hist["ORDEM"] = hist["ORDEM"].astype(int)
    return hist.sort_values(["ORDEM", "CONTAGEM"], ascending=[True, False]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def contagem_faixa_risco(df: pd.DataFrame) -> dict:
    """Contagem por faixa de risco (para os cartões da matriz de aging)."""
    if df.empty:
        return {faixa: 0 for faixa in ORDEM_FAIXA_RISCO}
    contagens = df["FAIXA_RISCO"].value_counts().to_dict()
    return {faixa: int(contagens.get(faixa, 0)) for faixa in ORDEM_FAIXA_RISCO}


@st.cache_data(show_spinner=False)
def financeiro_por_faixa(df: pd.DataFrame, ticket: float) -> pd.DataFrame:
    """MRR em risco por faixa de aging, com ordem canônica e rótulo formatado."""
    if df.empty:
        return pd.DataFrame(columns=["FAIXA_RISCO", "LINHAS", "MRR_RISCO", "MRR_LABEL"])
    base = df.groupby("FAIXA_RISCO")["NUMTELEFONE"].count().reset_index(name="LINHAS")
    base["MRR_RISCO"] = base["LINHAS"] * ticket
    ordem = {faixa: i for i, faixa in enumerate(ORDEM_FAIXA_RISCO)}
    base["_ordem"] = base["FAIXA_RISCO"].map(ordem).fillna(99)
    base = base.sort_values("_ordem").drop(columns="_ordem").reset_index(drop=True)
    base["MRR_LABEL"] = base["MRR_RISCO"].apply(_fmt_brl)
    return base


@st.cache_data(show_spinner=False)
def _moda(serie: pd.Series, padrao: str = "N/I") -> str:
    """Valor mais frequente da série (devolve `padrao` quando não há moda)."""
    moda = serie.mode()
    return moda.iloc[0] if len(moda) > 0 else padrao


@st.cache_data(show_spinner=False)
def clientes_agregados(df: pd.DataFrame) -> pd.DataFrame:
    """Ranking de clientes (linhas, tempo médio suspenso, UF/status predominantes)."""
    if df.empty:
        return pd.DataFrame(columns=["CLIENTE", "CNPJ_FORMATADO", "TOTAL_LINHAS",
                                     "TEMPO_MEDIO_SUSPENSO", "UF_PREDOMINANTE",
                                     "STATUS_PREDOMINANTE"])
    agg = df.groupby(["CLIENTE", "CNPJ_FORMATADO"]).agg(
        TOTAL_LINHAS=("NUMTELEFONE", "count"),
        TEMPO_MEDIO_SUSPENSO=("TEMPO_SUSPENSAO", "mean"),
        UF_PREDOMINANTE=("UF", _moda),
        STATUS_PREDOMINANTE=("STATUS", _moda),
    ).reset_index().sort_values("TOTAL_LINHAS", ascending=False).reset_index(drop=True)
    agg["LINHAS_ACUMULADAS"] = agg["TOTAL_LINHAS"].cumsum()
    total = agg["TOTAL_LINHAS"].sum()
    agg["PCT_ACUMULADO"] = (agg["LINHAS_ACUMULADAS"] / total * 100) if total else 0.0
    return agg


@st.cache_data(show_spinner=False)
def geo_por_uf(df: pd.DataFrame) -> pd.DataFrame:
    """Volume e tempo médio por UF."""
    if df.empty:
        return pd.DataFrame(columns=["UF", "TOTAL_LINHAS", "TEMPO_MEDIO"])
    return (
        df.groupby("UF").agg(TOTAL_LINHAS=("NUMTELEFONE", "count"),
                             TEMPO_MEDIO=("TEMPO_SUSPENSAO", "mean"))
        .reset_index().sort_values("TOTAL_LINHAS", ascending=False).reset_index(drop=True)
    )


@st.cache_data(show_spinner=False)
def geo_por_ddd(df: pd.DataFrame, limite: int = 12) -> pd.DataFrame:
    """Top DDDs por volume."""
    if df.empty:
        return pd.DataFrame(columns=["DDD", "UF", "CONTAGEM"])
    return (
        df.groupby(["DDD", "UF"])["NUMTELEFONE"].count().reset_index(name="CONTAGEM")
        .sort_values("CONTAGEM", ascending=False).head(limite).reset_index(drop=True)
    )


def _fmt_brl(valor: float) -> str:
    """Formata valores em reais no padrão brasileiro (R$ 1.234)."""
    return f"R$ {valor:,.0f}".replace(",", ".")


# ===================== ALERTAS E TENDÊNCIAS (CACHEADO) =====================

@st.cache_data(show_spinner=False, max_entries=4)
def serie_mensal(df_base: pd.DataFrame, ticket_medio: float = 45.0) -> pd.DataFrame:
    """Série mensal (volume, criticidade, MRR, variação MoM e média móvel) — cacheada."""
    from alertas import series_mensais
    return series_mensais(df_base, ticket_medio)


@st.cache_data(show_spinner=False, max_entries=4)
def alertas_do_painel(df_base: pd.DataFrame, ticket_medio: float = 45.0) -> list[dict]:
    """Alertas automáticos do recorte, já como dicionários (serializáveis pelo cache)."""
    from alertas import detectar_alertas, series_mensais
    serie = series_mensais(df_base, ticket_medio)
    return [dict(alerta._asdict()) for alerta in detectar_alertas(serie, df_base, ticket_medio)]


# ===================== MODELO PREDITIVO (CACHEADO) =====================

@st.cache_data(show_spinner=False, max_entries=4)
def propensao_recuperacao(df_base: pd.DataFrame) -> dict:
    """Treina e aplica o modelo de propensão de recuperação (cacheado).

    O treino é caro (Newton-Raphson sobre ~1,6 mil linhas + engenharia de features),
    então o resultado é cacheado pela base completa — não pelo recorte filtrado.
    """
    from modelo_risco import analisar
    return analisar(df_base)


# ===================== PDF CACHEADO =====================

@st.cache_data(show_spinner=False, max_entries=8)
def pdf_do_recorte(df: pd.DataFrame, ticket: float, referencia: str) -> bytes:
    """Gera (e cacheia) o PDF executivo do recorte atual."""
    from relatorio_pdf import gerar_pdf
    return gerar_pdf(df, ticket, referencia)
