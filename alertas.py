"""Motor de alertas automáticos e séries de tendência.

Objetivo
--------
Transformar a base mensal em **sinais acionáveis**: em vez de o gestor precisar
comparar meses mentalmente, o painel aponta o que mudou, com a regra explícita que
disparou cada alerta (auditável e testável).

Cada alerta carrega o nível, o título, o número que o motivou e a **regra** em texto,
para que ninguém precise confiar em uma "caixa preta".
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd

from logging_config import get_logger

log = get_logger("alertas")

# Tolerância (dias) entre o 1º dia do mês de referência e a extração implícita.
# Mantida em sincronia com `etl_pipeline.TOLERANCIA_EXTRACAO_DIAS`.
TOLERANCIA_EXTRACAO_DIAS = 45

# Níveis possíveis, em ordem de severidade (usados para cor e ordenação na UI)
NIVEIS = ["critico", "atencao", "positivo", "info"]

# Faixas de aging consideradas críticas (mesmo critério de app_data.AGING_CRITICO)
AGING_CRITICO = ["De 61 a 90 dias", "De 91 a 120 dias", "Maior que 120 dias"]

# --------------------- parâmetros das regras (explícitos e ajustáveis) ---------------------
FATOR_PICO = 1.5          # volume do mês > média histórica × 1,5  → pico
FATOR_QUEDA = 0.8         # volume do mês < média histórica × 0,8  → queda relevante
MESES_ALTA_SEGUIDA = 3    # meses consecutivos de alta                     → tendência de alta
LIMITE_PCT_CRITICO = 35.0  # % de linhas em aging crítico acima do qual alerta
LIMITE_CONCENTRACAO = 40.0  # % das linhas nos 5 maiores clientes
LIMITE_TELEFONE_INVALIDO = 5.0  # % de telefones inválidos
MIN_MESES_TENDENCIA = 3   # meses mínimos para avaliar tendência


class Alerta(NamedTuple):
    """Um sinal acionável com rastreabilidade da regra que o gerou."""

    nivel: str       # "critico" | "atencao" | "positivo" | "info"
    titulo: str
    detalhe: str
    valor: str
    regra: str


# ===================== SÉRIES =====================

def series_mensais(df_base: pd.DataFrame, ticket_medio: float = 45.0) -> pd.DataFrame:
    """Série mensal consolidada: volume, clientes, criticidade e MRR em risco.

    Returns:
        DataFrame ordenado cronologicamente com uma linha por mês de referência.
    """
    colunas = ["REFERENCIA_LABEL", "ORDEM", "LINHAS", "CLIENTES", "CRITICAS",
               "PCT_CRITICO", "TEMPO_MEDIO", "MRR_RISCO"]
    if df_base is None or df_base.empty:
        return pd.DataFrame(columns=colunas)

    dados = df_base.copy()
    dados["_critico"] = dados["AGING_LIMPO"].isin(AGING_CRITICO)

    serie = (
        dados.groupby(["REFERENCIA", "REFERENCIA_LABEL"])
        .agg(
            LINHAS=("NUMTELEFONE", "size"),
            CLIENTES=("CLIENTE", "nunique"),
            CRITICAS=("_critico", "sum"),
            TEMPO_MEDIO=("TEMPO_SUSPENSAO", "mean"),
        )
        .reset_index()
        .rename(columns={"REFERENCIA": "ORDEM"})
        .sort_values("ORDEM")
        .reset_index(drop=True)
    )
    serie["PCT_CRITICO"] = (serie["CRITICAS"] / serie["LINHAS"] * 100).round(1)
    serie["MRR_RISCO"] = serie["LINHAS"] * ticket_medio
    serie["TEMPO_MEDIO"] = serie["TEMPO_MEDIO"].round(1)

    # Variação mês a mês + média móvel de 3 meses
    serie["VAR_MOM_%"] = (serie["LINHAS"].pct_change() * 100).round(1)
    serie["MM3"] = serie["LINHAS"].rolling(window=3, min_periods=1).mean().round(1)

    return serie[colunas + ["VAR_MOM_%", "MM3"]]


# ===================== REGRAS =====================

def _media_anterior(serie: pd.DataFrame) -> float:
    """Média de volume dos meses anteriores ao último (exclui o mês avaliado)."""
    if len(serie) < 2:
        return float(serie["LINHAS"].mean()) if len(serie) else 0.0
    return float(serie["LINHAS"].iloc[:-1].mean())


def detectar_alertas(serie: pd.DataFrame, df_base: pd.DataFrame,
                     ticket_medio: float = 45.0) -> list[Alerta]:
    """Aplica o conjunto de regras e devolve os alertas ordenados por severidade.

    Args:
        serie: saída de `series_mensais`.
        df_base: base completa (para regras de concentração e qualidade).
        ticket_medio: usado para dimensionar o impacto financeiro em texto.
    """
    alertas: list[Alerta] = []
    if serie is None or serie.empty:
        return [Alerta("info", "Sem dados", "A base está vazia.", "—", "base vazia")]

    ultimo = serie.iloc[-1]
    media = _media_anterior(serie)
    rotulo_ultimo = str(ultimo["REFERENCIA_LABEL"])

    # R1 — Pico de volume
    if media > 0:
        razao = ultimo["LINHAS"] / media
        if razao > FATOR_PICO:
            alertas.append(Alerta(
                "critico", "Pico de volume no mês",
                f"{rotulo_ultimo} tem {ultimo['LINHAS']:,} linhas suspensas, "
                f"{razao:.2f}× a média dos meses anteriores ({media:,.0f}).",
                f"+{(razao - 1) * 100:.0f}% sobre a média",
                f"volume do mês > média histórica × {FATOR_PICO}",
            ))

    # R2 — Queda relevante
    if media > 0:
        razao = ultimo["LINHAS"] / media
        if razao < FATOR_QUEDA:
            alertas.append(Alerta(
                "positivo", "Queda de volume no mês",
                f"{rotulo_ultimo} tem {ultimo['LINHAS']:,} linhas, "
                f"{razao:.2f}× a média dos meses anteriores ({media:,.0f}). "
                "Sinal de recuperação — vale confirmar com o rastreador.",
                f"{(razao - 1) * 100:.0f}% vs média",
                f"volume do mês < média histórica × {FATOR_QUEDA}",
            ))

    # R3 — Alta consecutiva
    if len(serie) >= MESES_ALTA_SEGUIDA:
        variacoes = serie["VAR_MOM_%"].dropna().tail(MESES_ALTA_SEGUIDA - 1)
        if len(variacoes) == MESES_ALTA_SEGUIDA - 1 and (variacoes > 0).all():
            alertas.append(Alerta(
                "atencao", "Alta consecutiva do parque suspenso",
                f"{MESES_ALTA_SEGUIDA} meses seguidos de crescimento: "
                f"variações de {', '.join(f'{v:+.1f}%' for v in variacoes)}.",
                f"{serie['LINHAS'].iloc[-MESES_ALTA_SEGUIDA]:,} → {ultimo['LINHAS']:,} linhas",
                f"{MESES_ALTA_SEGUIDA} variações mensais positivas consecutivas",
            ))

    # R4 — Criticidade alta (aging avançado)
    if ultimo["PCT_CRITICO"] > LIMITE_PCT_CRITICO:
        alertas.append(Alerta(
            "critico", "Criticidade alta no mês",
            f"{ultimo['PCT_CRITICO']:.1f}% das linhas estão acima de 60 dias de suspensão "
            f"({ultimo['CRITICAS']:,} de {ultimo['LINHAS']:,}). Risco elevado de perda definitiva.",
            f"{ultimo['PCT_CRITICO']:.1f}% crítico",
            f"% de aging crítico > {LIMITE_PCT_CRITICO:.0f}%",
        ))
    elif ultimo["PCT_CRITICO"] < LIMITE_PCT_CRITICO / 2:
        alertas.append(Alerta(
            "positivo", "Criticidade sob controle",
            f"Apenas {ultimo['PCT_CRITICO']:.1f}% das linhas estão acima de 60 dias.",
            f"{ultimo['PCT_CRITICO']:.1f}% crítico",
            f"% de aging crítico < {LIMITE_PCT_CRITICO / 2:.0f}%",
        ))

    # R5 — Concentração em poucos clientes
    if df_base is not None and not df_base.empty:
        por_cliente = (
            df_base[df_base["REFERENCIA"] == ultimo["ORDEM"]]
            .groupby("CLIENTE")["NUMTELEFONE"].size().sort_values(ascending=False)
        )
        if len(por_cliente):
            top5 = float(por_cliente.head(5).sum()) / float(por_cliente.sum()) * 100
            if top5 > LIMITE_CONCENTRACAO:
                alertas.append(Alerta(
                    "atencao", "Concentração em poucos clientes",
                    f"Os 5 maiores clientes respondem por {top5:.1f}% das linhas suspensas "
                    f"de {rotulo_ultimo}. Perda de uma conta única tem impacto relevante.",
                    f"{top5:.1f}% nas top 5 contas",
                    f"% das linhas nos 5 maiores clientes > {LIMITE_CONCENTRACAO:.0f}%",
                ))

    # R6 — Qualidade da base: telefone inválido
    if df_base is not None and "NUMTELEFONE_STR" in df_base.columns and not df_base.empty:
        telefones = df_base["NUMTELEFONE_STR"].astype(str)
        invalidos = ((telefones.str.len() < 10) | (telefones == "nan")).sum()
        pct_invalidos = invalidos / len(df_base) * 100
        if pct_invalidos > LIMITE_TELEFONE_INVALIDO:
            alertas.append(Alerta(
                "atencao", "Telefones inválidos ou ausentes",
                f"{invalidos:,} registro(s) ({pct_invalidos:.1f}%) sem telefone utilizável — "
                "esses clientes não podem ser acionados por WhatsApp.",
                f"{pct_invalidos:.1f}% inválidos",
                f"% de telefones inválidos > {LIMITE_TELEFONE_INVALIDO:.0f}%",
            ))

    # R7 — Qualidade: duplicatas exatas
    if df_base is not None and not df_base.empty:
        duplicatas = int(df_base.duplicated().sum())
        if duplicatas > 0:
            alertas.append(Alerta(
                "critico", "Duplicatas na base tratada",
                f"{duplicatas:,} registro(s) 100% idênticos. Reexecute o ETL para "
                "deduplicar antes de tomar decisões de volume.",
                f"{duplicatas:,} duplicatas",
                "duplicatas exatas > 0",
            ))

    # R8 — Defasagem da base
    if len(serie) == 1:
        alertas.append(Alerta(
            "info", "Base com um único mês",
            "Comparações mês a mês e tendências ficam indisponíveis. Ingira mais um mês "
            "para habilitar as análises de evolução.",
            "1 mês",
            f"menos de {MIN_MESES_TENDENCIA} meses na base",
        ))

    # R9 — Consistência da data de extração por bloco mensal
    if df_base is not None and not df_base.empty:
        try:
            from etl_pipeline import descrever_extracao, extracoes_por_mes

            extracoes = extracoes_por_mes(df_base)
            for _, linha in extracoes[~extracoes["CONSISTENTE"]].iterrows():
                desvio = linha["DESVIO_DIAS"]
                valor = (f"{int(desvio):+d} dias de desvio" if pd.notna(desvio)
                         else "data de extração indeterminada")
                alertas.append(Alerta(
                    "atencao", f"Aging de {linha['REFERENCIA_LABEL']} fora do período",
                    f"O bloco de {linha['REFERENCIA_LABEL']} teve a coluna de tempo de "
                    f"suspensão calculada em outro momento ({descrever_extracao(linha)}). "
                    "O aging — e portanto a criticidade e o MRR em risco — desse mês não é "
                    "comparável com os demais. Solicite a reextração corrigida à origem ou "
                    "ative a normalização no ETL.",
                    valor,
                    f"|data de extração − 1º dia do mês| > {TOLERANCIA_EXTRACAO_DIAS} dias",
                ))
        except Exception as erro:  # nunca derrubar o painel por causa de um alerta
            log.warning("Não foi possível avaliar a consistência da extração: %s", erro)

    alertas.sort(key=lambda a: NIVEIS.index(a.nivel) if a.nivel in NIVEIS else 99)
    log.info("Alertas detectados: %s", {a.titulo for a in alertas} or "nenhum")
    return alertas


def resumo_alertas(alertas: list[Alerta]) -> dict:
    """Contagem por nível, para os cartões de resumo da central de alertas."""
    return {nivel: sum(1 for a in alertas if a.nivel == nivel) for nivel in NIVEIS}
