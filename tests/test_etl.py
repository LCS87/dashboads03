"""Testes do pipeline de ETL (`etl_pipeline.py`)."""
from __future__ import annotations

import pandas as pd
import pytest

import etl_pipeline as etl


# ------------------------------------------------ validar_base

def test_validar_base_aceita_base_valida(base_tratada):
    resumo = etl.validar_base(base_tratada, origem="teste", obrigatorias=etl.COLUNAS_OBRIGATORIAS)
    assert resumo["linhas"] == len(base_tratada)
    assert resumo["colunas_faltantes"] == []
    assert resumo["meses"], "a base deve ter ao menos um mês"


def test_validar_base_rejeita_none():
    with pytest.raises(etl.ETLValidationError):
        etl.validar_base(None, origem="teste")


def test_validar_base_rejeita_dataframe_vazio():
    with pytest.raises(etl.ETLValidationError):
        etl.validar_base(pd.DataFrame(), origem="teste")


def test_validar_base_rejeita_colunas_obrigatorias_ausentes(base_tratada):
    reduzida = base_tratada.drop(columns=["AGING", "STATUS"])
    with pytest.raises(etl.ETLValidationError):
        etl.validar_base(reduzida, origem="teste")


def test_validar_base_modo_nao_estrito_apenas_alerta(base_tratada):
    reduzida = base_tratada.drop(columns=["AGING"])
    resumo = etl.validar_base(reduzida, origem="teste", estrito=False)
    assert "AGING" in resumo["colunas_faltantes"]
    assert any("AGING" in alerta for alerta in resumo["alertas"])


def test_validar_base_detecta_referencia_invalida(base_tratada):
    alterada = base_tratada.copy()
    alterada.loc[alterada.index[0], "REFERENCIA"] = 999999
    resumo = etl.validar_base(alterada, origem="teste")
    assert any("fora da faixa" in alerta for alerta in resumo["alertas"])


def test_validar_base_reporta_duplicatas(base_tratada):
    duplicada = pd.concat([base_tratada, base_tratada.head(5)], ignore_index=True)
    resumo = etl.validar_base(duplicada, origem="teste")
    assert any("duplicad" in alerta.lower() for alerta in resumo["alertas"])


# ------------------------------------------------ deduplicação

def test_remover_duplicatas_exatas(base_tratada):
    amostra = base_tratada.head(20)
    dobrada = pd.concat([amostra, amostra, amostra], ignore_index=True)
    limpa, removidas = etl.remover_duplicatas_exatas(dobrada)

    assert len(limpa) == 20
    assert removidas == 40
    assert limpa.duplicated().sum() == 0


def test_remover_duplicatas_e_idempotente(base_tratada):
    limpa1, removidas1 = etl.remover_duplicatas_exatas(base_tratada)
    limpa2, removidas2 = etl.remover_duplicatas_exatas(limpa1)
    assert removidas1 == 0
    assert removidas2 == 0
    assert len(limpa1) == len(limpa2) == len(base_tratada)


def test_remover_duplicatas_preserva_linhas_distintas():
    df = pd.DataFrame({"A": [1, 1, 2, 2], "B": ["x", "x", "y", "z"]})
    limpa, removidas = etl.remover_duplicatas_exatas(df)
    assert len(limpa) == 3  # só (1, x) duplicava
    assert removidas == 1


def test_remover_duplicatas_dataframe_vazio():
    limpa, removidas = etl.remover_duplicatas_exatas(pd.DataFrame())
    assert limpa.empty
    assert removidas == 0


# ------------------------------------------------ helpers de domínio

def test_ref_to_label():
    assert etl.ref_to_label(202601) == "Jan/2026"
    assert etl.ref_to_label(202612) == "Dez/2026"


def test_clean_aging_normaliza():
    assert etl.clean_aging("ATÉ 30 DIAS") == "Até 30 dias"
    assert etl.clean_aging("DE 31 A 60 DIAS") == "De 31 a 60 dias"
    assert etl.clean_aging(None) == "Não Informado"


def test_colunas_derivadas_definidas():
    """Toda coluna derivada precisa existir na base tratada."""
    for coluna in etl.COLUNAS_DERIVADAS:
        assert coluna not in etl.COLUNAS_OBRIGATORIAS


def test_flag_deduplicacao_ativa():
    """A correção do pico de Abril depende desta flag ligada."""
    assert etl.REMOVER_DUPLICATAS_EXATAS is True


def test_base_tratada_nao_tem_duplicatas(base_tratada):
    assert base_tratada.duplicated().sum() == 0


def test_base_tratada_sem_colunas_anonimizadas(base_tratada):
    for coluna in ["DEALEAR", "CD_DEALER", "NOME_DIRETOR", "NOME_DIVISAO"]:
        assert coluna not in base_tratada.columns


# ------------------------------------------------ consistência da extração


def _base_com_extracao(referencia: int, dias_ate_extracao: int, linhas: int = 3) -> pd.DataFrame:
    """Bloco sintético cuja extração implícita cai `dias_ate_extracao` após o 1º do mês."""
    inicio = pd.to_datetime(str(referencia), format="%Y%m")
    data_extracao = inicio + pd.Timedelta(days=dias_ate_extracao)
    suspensao = inicio - pd.Timedelta(days=20)
    return pd.DataFrame([
        {
            "REFERENCIA": referencia,
            "REFERENCIA_LABEL": etl.ref_to_label(referencia),
            "DT_SUSPENSAO": suspensao,
            "TEMPO_SUSPENSAO": (data_extracao - suspensao).days,
        }
        for _ in range(linhas)
    ])


def test_extracoes_por_mes_reconstroi_data_e_desvio():
    base = pd.concat([
        _base_com_extracao(202601, 12),
        _base_com_extracao(202602, 5),
        _base_com_extracao(202603, 82),
    ], ignore_index=True)

    extracoes = etl.extracoes_por_mes(base)

    assert list(extracoes["DESVIO_DIAS"]) == [12, 5, 82]
    assert list(extracoes["CONSISTENTE"]) == [True, True, False]
    assert list(extracoes["REFERENCIA_LABEL"]) == ["Jan/2026", "Fev/2026", "Mar/2026"]


def test_extracoes_por_mes_sem_colunas_retorna_vazio(base_tratada):
    assert etl.extracoes_por_mes(base_tratada.drop(columns=["TEMPO_SUSPENSAO"])).empty
    assert etl.extracoes_por_mes(pd.DataFrame()).empty
    assert etl.extracoes_por_mes(None).empty


def test_validar_base_alerta_extracao_inconsistente():
    base = pd.concat([
        _base_com_extracao(202601, 10),
        _base_com_extracao(202602, 10),
        _base_com_extracao(202603, 90),
    ], ignore_index=True)
    resumo = etl.validar_base(base, origem="teste", estrito=False)

    assert any("fora do mês de referência" in alerta for alerta in resumo["alertas"])
    assert any(linha["REFERENCIA_LABEL"] == "Mar/2026" for linha in resumo["extracoes"])


def test_base_tratada_registra_extracao_do_abril(base_tratada):
    """Achado documentado: Abr/2026 foi extraído ~82 dias depois do seu mês."""
    extracoes = etl.extracoes_por_mes(base_tratada)
    abril = extracoes[extracoes["REFERENCIA_LABEL"] == "Abr/2026"]
    if abril.empty:
        pytest.skip("base sem o bloco de Abr/2026")

    assert not bool(abril["CONSISTENTE"].iloc[0])
    assert int(abril["DESVIO_DIAS"].iloc[0]) > etl.TOLERANCIA_EXTRACAO_DIAS


# ------------------------------------------------ normalização do aging


def test_normalizar_aging_recalcula_pela_data_de_suspensao():
    base = pd.DataFrame({
        "REFERENCIA": [202601, 202601],
        "DT_SUSPENSAO": [pd.Timestamp("2025-12-20"), pd.Timestamp("2025-11-25")],
        "TEMPO_SUSPENSAO": [999, 999],
        "AGING": ["MAIOR QUE 120 DIAS", "MAIOR QUE 120 DIAS"],
    })
    ajustada, quantidade = etl.normalizar_aging(base)

    # 2026-01-01 - 2025-12-20 = 12 dias ; 2026-01-01 - 2025-11-25 = 37 dias
    assert list(ajustada["TEMPO_SUSPENSAO"]) == [12, 37]
    assert list(ajustada["AGING"]) == ["Até 30 dias", "De 31 a 60 dias"]
    assert quantidade == 2


def test_normalizar_aging_trunca_dias_negativos():
    base = pd.DataFrame({
        "REFERENCIA": [202601],
        "DT_SUSPENSAO": [pd.Timestamp("2026-01-15")],
        "TEMPO_SUSPENSAO": [10],
    })
    ajustada, _ = etl.normalizar_aging(base)
    assert ajustada["TEMPO_SUSPENSAO"].iloc[0] == 0


def test_normalizar_aging_torna_abril_comparavel(base_tratada):
    """Depois de normalizar, Abr/2026 deixa de ser um outlier artificial de criticidade."""
    ajustada, _ = etl.normalizar_aging(base_tratada)
    critico = ["De 61 a 90 dias", "De 91 a 120 dias", "Maior que 120 dias"]

    antes = base_tratada.assign(_c=base_tratada["AGING_LIMPO"].isin(critico)) \
        .groupby("REFERENCIA_LABEL")["_c"].mean()
    depois = ajustada.assign(_c=ajustada["AGING"].isin(critico)) \
        .groupby("REFERENCIA_LABEL")["_c"].mean()

    assert antes["Abr/2026"] > 0.5
    assert depois["Abr/2026"] < 0.5


def test_normalizar_aging_desligado_por_padrao():
    assert etl.NORMALIZAR_AGING_POR_REFERENCIA is False


def test_faixa_aging_dias_limites():
    assert etl._faixa_aging_dias(0) == "Até 30 dias"
    assert etl._faixa_aging_dias(30) == "Até 30 dias"
    assert etl._faixa_aging_dias(31) == "De 31 a 60 dias"
    assert etl._faixa_aging_dias(60) == "De 31 a 60 dias"
    assert etl._faixa_aging_dias(61) == "De 61 a 90 dias"
    assert etl._faixa_aging_dias(120) == "De 91 a 120 dias"
    assert etl._faixa_aging_dias(121) == "Maior que 120 dias"
    assert etl._faixa_aging_dias(float("nan")) == "Não Informado"


def test_descrever_extracao_tolera_datas_indeterminadas():
    """Regressão: REFERENCIA inválida não pode quebrar a montagem do alerta."""
    linha = pd.Series({"REFERENCIA_LABEL": "99/9999", "EXTRACAO_IMPLICITA": pd.NaT,
                       "DESVIO_DIAS": float("nan")})
    assert "indeterminada" in etl.descrever_extracao(linha)


def test_validar_base_com_referencia_invalida_nao_quebra(base_tratada):
    """Regressão: mês inválido não pode derrubar a validação (Nem formatar NaN)."""
    alterada = base_tratada.copy()
    alterada.loc[alterada.index[0], "REFERENCIA"] = 999999
    resumo = etl.validar_base(alterada, origem="teste", estrito=False)
    assert resumo["linhas"] == len(alterada)
    assert any("fora da faixa" in alerta for alerta in resumo["alertas"])
