"""Testes do motor de alertas e das séries de tendência (`alertas.py`)."""
from __future__ import annotations

import pandas as pd
import pytest

import alertas as al
from etl_pipeline import ref_to_label


# ------------------------------------------------ construtores sintéticos

def _linha(referencia: int, indice: int, aging: str = "Até 30 dias",
           tempo: int = 10, telefone: str | None = None, cliente: str | None = None) -> dict:
    """Uma linha de base sintética com as colunas que o motor consome.

    A data de suspensão é derivada para que `DT_SUSPENSAO + TEMPO_SUSPENSAO` caia no
    primeiro dia do mês de referência — ou seja, o bloco é "consistente" por construção.
    """
    mes, ano = referencia % 100, referencia // 100
    return {
        "REFERENCIA": referencia,
        "REFERENCIA_LABEL": ref_to_label(referencia),
        "NUMTELEFONE": int(telefone or f"8198{indice:07d}"),
        "NUMTELEFONE_STR": str(telefone or f"8198{indice:07d}"),
        "CLIENTE": cliente or f"CLIENTE {indice % 7}",
        "AGING_LIMPO": aging,
        "TEMPO_SUSPENSAO": tempo,
        "DT_SUSPENSAO": pd.Timestamp(year=ano, month=mes, day=1) - pd.Timedelta(days=tempo),
    }


def _base(volumes: dict[int, int], aging: str = "Até 30 dias", tempo: int = 10) -> pd.DataFrame:
    """Base sintética: {referencia: quantidade_de_linhas}."""
    registros = []
    indice = 0
    for referencia, quantidade in volumes.items():
        for _ in range(quantidade):
            indice += 1
            registros.append(_linha(referencia, indice, aging=aging, tempo=tempo))
    return pd.DataFrame(registros)


# ------------------------------------------------ séries

def test_series_mensais_estrutura_e_ordenacao():
    serie = al.series_mensais(_base({202601: 10, 202602: 12, 202603: 11}), ticket_medio=50.0)

    assert list(serie["LINHAS"]) == [10, 12, 11]
    assert serie["ORDEM"].is_monotonic_increasing
    assert list(serie["MRR_RISCO"]) == [500.0, 600.0, 550.0]
    assert pd.isna(serie["VAR_MOM_%"].iloc[0])  # primeiro mês não tem mês anterior
    assert serie["VAR_MOM_%"].iloc[1] == pytest.approx(20.0)
    assert set(["MM3", "PCT_CRITICO", "CLIENTES"]).issubset(serie.columns)


def test_series_mensais_media_movel_de_3():
    serie = al.series_mensais(_base({202601: 3, 202602: 6, 202603: 9, 202604: 12}))
    # MM3: [3, 4.5, 6, 9]
    assert list(serie["MM3"]) == [3.0, 4.5, 6.0, 9.0]


def test_series_mensais_conta_criticos():
    base = pd.concat([
        _base({202601: 4}, aging="Até 30 dias"),
        _base({202601: 6}, aging="Maior que 120 dias"),
    ], ignore_index=True)
    serie = al.series_mensais(base)
    assert serie["LINHAS"].iloc[0] == 10
    assert serie["CRITICAS"].iloc[0] == 6
    assert serie["PCT_CRITICO"].iloc[0] == pytest.approx(60.0)


def test_series_mensais_vazia():
    serie = al.series_mensais(pd.DataFrame())
    assert serie.empty
    assert "LINHAS" in serie.columns


# ------------------------------------------------ regras isoladas

def _alertas(base: pd.DataFrame, ticket: float = 45.0) -> list[al.Alerta]:
    return al.detectar_alertas(al.series_mensais(base, ticket), base, ticket)


def test_regra_pico_dispara():
    alertas = _alertas(_base({202601: 100, 202602: 100, 202603: 100, 202604: 400}))
    titulos = [a.titulo for a in alertas]
    assert "Pico de volume no mês" in titulos
    pico = next(a for a in alertas if a.titulo == "Pico de volume no mês")
    assert pico.nivel == "critico"
    assert str(al.FATOR_PICO) in pico.regra


def test_regra_pico_nao_dispara_em_serie_estavel():
    alertas = _alertas(_base({202601: 100, 202602: 100, 202603: 100, 202604: 100}))
    assert "Pico de volume no mês" not in [a.titulo for a in alertas]


def test_regra_queda_dispara_como_positivo():
    alertas = _alertas(_base({202601: 200, 202602: 200, 202603: 200, 202604: 100}))
    queda = next((a for a in alertas if a.titulo == "Queda de volume no mês"), None)
    assert queda is not None
    assert queda.nivel == "positivo"


def test_regra_alta_consecutiva():
    alertas = _alertas(_base({202601: 100, 202602: 110, 202603: 120, 202604: 130}))
    assert "Alta consecutiva do parque suspenso" in [a.titulo for a in alertas]


def test_regra_criticidade_alta():
    base = _base({202601: 10, 202602: 10}, aging="Maior que 120 dias")
    alertas = _alertas(base)
    critico = next(a for a in alertas if a.titulo == "Criticidade alta no mês")
    assert critico.nivel == "critico"
    assert f"{al.LIMITE_PCT_CRITICO:.0f}%" in critico.regra


def test_regra_criticidade_controlada():
    base = _base({202601: 10, 202602: 10}, aging="Até 30 dias")
    alertas = _alertas(base)
    assert "Criticidade sob controle" in [a.titulo for a in alertas]


def test_regra_concentracao():
    base = _base({202601: 5, 202602: 5}, aging="Até 30 dias")
    # Todas as linhas do último mês pertencem a um único cliente
    base.loc[base["REFERENCIA"] == 202602, "CLIENTE"] = "GRANDE CONTA"
    alertas = _alertas(base)
    assert "Concentração em poucos clientes" in [a.titulo for a in alertas]


def test_regra_telefone_invalido():
    base = _base({202601: 8, 202602: 8}, aging="Até 30 dias")
    base.loc[base.index[:3], "NUMTELEFONE_STR"] = "123"
    alertas = _alertas(base)
    assert "Telefones inválidos ou ausentes" in [a.titulo for a in alertas]


def test_regra_duplicatas():
    base = _base({202601: 5, 202602: 5}, aging="Até 30 dias")
    base = pd.concat([base, base.head(1)], ignore_index=True)
    alertas = _alertas(base)
    critico = next((a for a in alertas if a.titulo == "Duplicatas na base tratada"), None)
    assert critico is not None and critico.nivel == "critico"


def test_regra_um_unico_mes():
    alertas = _alertas(_base({202601: 10}, aging="Até 30 dias"))
    assert "Base com um único mês" in [a.titulo for a in alertas]


def test_regra_extracao_inconsistente(base_tratada):
    """A base real tem Abr/2026 extraído fora do mês — o alerta deve apontar."""
    alertas = _alertas(base_tratada)
    extracao = [a for a in alertas if "fora do período" in a.titulo]
    if not extracao:
        pytest.skip("base sem bloco mensal inconsistente")
    assert extracao[0].nivel == "atencao"
    assert "Abr/2026" in extracao[0].titulo


def test_base_vazia_devolve_alerta_informativo():
    alertas = al.detectar_alertas(pd.DataFrame(), pd.DataFrame())
    assert len(alertas) == 1
    assert alertas[0].nivel == "info"


def test_alertas_ordenados_por_severidade():
    base = pd.concat([
        _base({202601: 100}, aging="Até 30 dias"),
        _base({202602: 100}, aging="Maior que 120 dias"),
        _base({202603: 400}, aging="Maior que 120 dias"),
    ], ignore_index=True)
    alertas = _alertas(base)
    niveis = [al.NIVEIS.index(a.nivel) for a in alertas]
    assert niveis == sorted(niveis)


def test_alerta_carrega_regra_e_valor():
    alertas = _alertas(_base({202601: 100, 202602: 100, 202603: 100, 202604: 400}))
    for alerta in alertas:
        assert alerta.regra, f"alerta sem regra explícita: {alerta.titulo}"
        assert alerta.valor, f"alerta sem valor: {alerta.titulo}"
        assert alerta.nivel in al.NIVEIS


def test_resumo_alertas_conta_por_nivel():
    base = pd.concat([
        _base({202601: 100}, aging="Até 30 dias"),
        _base({202602: 100}, aging="Maior que 120 dias"),
        _base({202603: 500}, aging="Maior que 120 dias"),
    ], ignore_index=True)
    resumo = al.resumo_alertas(_alertas(base))
    assert set(resumo) == set(al.NIVEIS)
    assert sum(resumo.values()) == len(_alertas(base))
    assert resumo["critico"] >= 1


def test_serie_respeita_ticket_medio():
    serie = al.series_mensais(_base({202601: 10, 202602: 20}), ticket_medio=100.0)
    assert list(serie["MRR_RISCO"]) == [1000.0, 2000.0]
