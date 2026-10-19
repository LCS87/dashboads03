"""Testes das agregações cacheadas e regras de negócio (`app_data.py`)."""
from __future__ import annotations

import pandas as pd
import pytest

import app_data as ad


# ------------------------------------------------ KPIs

def test_resumo_kpis_consistente(base_tratada):
    kpis = ad.resumo_kpis(base_tratada)

    assert kpis["total_linhas"] == len(base_tratada)
    assert kpis["total_clientes"] == base_tratada["CLIENTE"].nunique()
    assert 0 <= kpis["total_inadimp"] <= kpis["total_linhas"]
    assert 0 <= kpis["pct_inadimp"] <= 100
    assert 0 <= kpis["pct_critico"] <= 100
    assert kpis["tempo_medio"] >= 0


def test_resumo_kpis_recorte_vazio():
    vazio = pd.DataFrame(columns=["STATUS", "AGING_LIMPO", "CLIENTE", "TEMPO_SUSPENSAO"])
    kpis = ad.resumo_kpis(vazio)
    assert kpis["total_linhas"] == 0
    assert kpis["pct_inadimp"] == 0.0


def test_pct_critico_calculado_sobre_aging_critico(base_tratada):
    kpis = ad.resumo_kpis(base_tratada)
    esperado = base_tratada["AGING_LIMPO"].isin(ad.AGING_CRITICO).sum() / len(base_tratada) * 100
    assert kpis["pct_critico"] == pytest.approx(esperado)


# ------------------------------------------------ faixas de risco

def test_contagem_faixa_risco_cobre_todas_as_faixas(base_tratada):
    contagem = ad.contagem_faixa_risco(base_tratada)
    assert set(contagem) == set(ad.ORDEM_FAIXA_RISCO)
    assert sum(contagem.values()) <= len(base_tratada)


def test_contagem_faixa_risco_vazio():
    vazio = pd.DataFrame(columns=["FAIXA_RISCO"])
    contagem = ad.contagem_faixa_risco(vazio)
    assert all(valor == 0 for valor in contagem.values())


def test_financeiro_por_faixa_aplica_ticket(base_tratada):
    tabela = ad.financeiro_por_faixa(base_tratada, ticket=50.0)
    assert not tabela.empty
    assert (tabela["MRR_RISCO"] == tabela["LINHAS"] * 50.0).all()
    assert tabela["MRR_LABEL"].str.startswith("R$").all()
    assert tabela["LINHAS"].sum() == len(base_tratada)


def test_financeiro_por_faixa_respeita_ordem_canonica(base_tratada):
    tabela = ad.financeiro_por_faixa(base_tratada, ticket=45.0)
    ordem = [f for f in ad.ORDEM_FAIXA_RISCO if f in set(tabela["FAIXA_RISCO"])]
    assert list(tabela["FAIXA_RISCO"]) == ordem


def test_financeiro_por_faixa_vazio():
    vazio = pd.DataFrame(columns=["FAIXA_RISCO", "NUMTELEFONE"])
    tabela = ad.financeiro_por_faixa(vazio, ticket=45.0)
    assert tabela.empty
    assert list(tabela.columns) == ["FAIXA_RISCO", "LINHAS", "MRR_RISCO", "MRR_LABEL"]


# ------------------------------------------------ históricos e clientes

def test_historico_mensal_ordenado_cronologicamente(base_tratada):
    hist = ad.historico_mensal(base_tratada)
    assert not hist.empty
    assert hist["ORDEM"].is_monotonic_increasing
    assert hist["CONTAGEM"].sum() == len(base_tratada)


def test_historico_mensal_soma_por_mes(base_tratada):
    hist = ad.historico_mensal(base_tratada)
    por_mes = hist.groupby("REFERENCIA_LABEL")["CONTAGEM"].sum()
    esperado = base_tratada["REFERENCIA_LABEL"].value_counts()
    for mes, valor in por_mes.items():
        assert valor == esperado[mes]


def test_clientes_agregados_ranking_e_pareto(base_tratada):
    tabela = ad.clientes_agregados(base_tratada)
    assert not tabela.empty
    assert tabela["TOTAL_LINHAS"].is_monotonic_decreasing
    assert tabela["TOTAL_LINHAS"].sum() == len(base_tratada)
    assert tabela["LINHAS_ACUMULADAS"].iloc[-1] == len(base_tratada)


def test_clientes_agregados_vazio():
    vazio = pd.DataFrame(columns=["CLIENTE", "CNPJ_FORMATADO", "NUMTELEFONE",
                                  "TEMPO_SUSPENSAO", "UF", "STATUS"])
    tabela = ad.clientes_agregados(vazio)
    assert tabela.empty


# ------------------------------------------------ geografia

def test_geo_por_uf_agrega_corretamente(base_tratada):
    tabela = ad.geo_por_uf(base_tratada)
    assert not tabela.empty
    assert tabela["TOTAL_LINHAS"].sum() == len(base_tratada)
    assert tabela["TOTAL_LINHAS"].is_monotonic_decreasing


def test_geo_por_ddd_respeita_limite(base_tratada):
    tabela = ad.geo_por_ddd(base_tratada, limite=5)
    assert len(tabela) <= 5
    assert {"DDD", "CONTAGEM"}.issubset(tabela.columns)


def test_qualidade_sem_duplicatas(base_tratada):
    resumo = ad.resumo_qualidade(base_tratada)
    assert resumo["duplicatas_exatas"] == 0
    assert not resumo["por_mes"].empty
    # Fator de multiplicação deve ser 1,0 quando não há duplicatas
    assert (resumo["por_mes"]["FATOR"] == 1.0).all()


# ------------------------------------------------ utilidades

def test_fmt_brl_formata_moeda():
    """Padrão brasileiro sem centavos (arredonda para inteiro)."""
    assert ad._fmt_brl(1234.5) == "R$ 1.234"
    assert ad._fmt_brl(0) == "R$ 0"
    assert ad._fmt_brl(1234567.0) == "R$ 1.234.567"


def test_pdf_do_recorte_gera_bytes(base_tratada):
    pdf = ad.pdf_do_recorte(base_tratada, ticket=45.0, referencia="Mai/2026")
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000
