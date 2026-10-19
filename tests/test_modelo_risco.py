"""Testes do modelo de propensão de recuperação (`modelo_risco.py`).

Incluem um teste de regressão **anti-vazamento**: se alguém voltar a usar meses
futuros para construir as features, a AUC dispara artificialmente (> 0,9) e o teste
`test_sem_vazamento_de_meses_futuros` falha.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import modelo_risco as mr


# ------------------------------------------------ AUC

def test_auc_ordenacao_perfeita():
    y = np.array([0, 0, 1, 1])
    assert mr.auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)


def test_auc_ordenacao_invertida():
    y = np.array([0, 0, 1, 1])
    assert mr.auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == pytest.approx(0.0)


def test_auc_empate_total_e_aleatorio():
    y = np.array([0, 0, 1, 1])
    assert mr.auc(y, np.array([0.5, 0.5, 0.5, 0.5])) == pytest.approx(0.5)


def test_auc_retorna_none_com_uma_classe_so():
    assert mr.auc(np.array([1, 1, 1]), np.array([0.2, 0.5, 0.9])) is None


def test_auc_esta_entre_0_e_1(base_tratada):
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 200)
    if y.min() == y.max():
        pytest.skip("amostra degenerada")
    assert 0.0 <= mr.auc(y, rng.random(200)) <= 1.0


# ------------------------------------------------ prioridade por tercis

def test_faixas_por_tercis_equilibradas():
    prob = np.linspace(0, 1, 300)
    faixas = mr.faixas_por_tercis(prob)
    contagem = pd.Series(faixas).value_counts()
    assert set(contagem.index) == set(mr.ROTULOS_PROPENSAO)
    for rotulo in mr.ROTULOS_PROPENSAO:
        assert contagem[rotulo] == pytest.approx(100, abs=2)


def test_faixas_por_tercis_preserva_ordem():
    prob = np.array([0.01, 0.02, 0.03, 0.97, 0.98, 0.99])
    faixas = mr.faixas_por_tercis(prob)
    assert faixas[0] == "Baixa"
    assert faixas[-1] == "Alta (Prioridade)"


def test_faixas_por_tercis_vazio_e_pequeno():
    assert mr.faixas_por_tercis(np.array([])).size == 0
    assert mr.faixas_por_tercis(np.array([0.5])).tolist() == ["Alta (Prioridade)"]


# ------------------------------------------------ construção do dataset

def test_construir_dataset_estrutura(base_tratada):
    dataset = mr.construir_dataset(base_tratada)
    assert not dataset.empty
    esperadas = {"REFERENCIA", "REFERENCIA_LABEL", "NUMTELEFONE_STR", "SAIU",
                 *mr.COLUNAS_NUMERICAS, *mr.COLUNAS_CATEGORICAS}
    assert esperadas.issubset(set(dataset.columns))
    assert len(dataset) == len(base_tratada)


def test_rotulo_nulo_apenas_no_ultimo_mes(base_tratada):
    dataset = mr.construir_dataset(base_tratada)
    ultimo = dataset["REFERENCIA"].max()
    sem_rotulo = dataset[dataset["SAIU"].isna()]
    assert (sem_rotulo["REFERENCIA"] == ultimo).all()
    assert dataset[dataset["REFERENCIA"] != ultimo]["SAIU"].notna().all()


def test_rotulo_e_binario(base_tratada):
    dataset = mr.construir_dataset(base_tratada)
    assert set(dataset["SAIU"].dropna().unique()) <= {0.0, 1.0}


def test_features_de_historico_nao_usam_meses_futuros(base_tratada):
    """No primeiro mês da base, nenhuma linha pode ter histórico acumulado > 1."""
    dataset = mr.construir_dataset(base_tratada)
    primeiro = dataset["REFERENCIA"].min()
    linhas_primeiro = dataset[dataset["REFERENCIA"] == primeiro]
    if linhas_primeiro.empty:
        pytest.skip("base sem primeiro mês identificável")
    assert (linhas_primeiro["MESES_CONSECUTIVOS"] <= 1).all()
    assert (linhas_primeiro["APARICOES_TOTAIS"] <= 1).all()


def test_meses_consecutivos_nao_excede_aparicoes(base_tratada):
    dataset = mr.construir_dataset(base_tratada)
    assert (dataset["MESES_CONSECUTIVOS"] <= dataset["APARICOES_TOTAIS"]).all()


def test_tenure_nao_negativo(base_tratada):
    dataset = mr.construir_dataset(base_tratada)
    assert (dataset["DIAS_DESDE_ATIVACAO"].dropna() >= 0).all()


def test_construir_dataset_vazio():
    assert mr.construir_dataset(pd.DataFrame()).empty
    assert mr.construir_dataset(None).empty


# ------------------------------------------------ modelo

def _dados_treino(base_tratada):
    dataset = mr.construir_dataset(base_tratada)
    rotulado = dataset[dataset["SAIU"].notna()]
    treino = rotulado[rotulado["REFERENCIA"] < rotulado["REFERENCIA"].max()]
    return treino


def test_modelo_treina_e_preve_probabilidades(base_tratada):
    treino = _dados_treino(base_tratada)
    if treino["SAIU"].nunique() < 2 or len(treino) < 20:
        pytest.skip("dados insuficientes")

    modelo = mr.ModeloRisco().fit(treino, treino["SAIU"])
    prob = modelo.predict_proba(treino)

    assert prob.shape == (len(treino),)
    assert ((prob >= 0) & (prob <= 1)).all()
    assert modelo.n_iter_ <= modelo.max_iter
    assert len(modelo.historico_logloss_) == modelo.n_iter_
    # A log-loss deve cair ao longo do treino (convergência)
    assert modelo.historico_logloss_[-1] <= modelo.historico_logloss_[0]


def test_modelo_predict_antes_de_fit_falha():
    with pytest.raises(RuntimeError):
        mr.ModeloRisco().predict_proba(pd.DataFrame({"x": [1]}))


def test_coeficientes_excluem_intercepto(base_tratada):
    treino = _dados_treino(base_tratada)
    if treino["SAIU"].nunique() < 2:
        pytest.skip("dados insuficientes")
    modelo = mr.ModeloRisco().fit(treino, treino["SAIU"])
    coeficientes = modelo.coeficientes()
    assert "intercepto" not in set(coeficientes["FEATURE"])
    assert {"FEATURE", "PESO", "EFEITO"}.issubset(coeficientes.columns)
    # Ordenado por importância absoluta
    assert coeficientes["PESO"].abs().is_monotonic_decreasing


def test_calibracao_de_intercepto_aproxima_media(base_tratada):
    treino = _dados_treino(base_tratada)
    if treino["SAIU"].nunique() < 2:
        pytest.skip("dados insuficientes")
    modelo = mr.ModeloRisco().fit(treino, treino["SAIU"])

    alvo = float(treino["SAIU"].mean())
    modelo.calibrar_intercepto(treino, alvo)
    assert modelo.predict_proba(treino).mean() == pytest.approx(alvo, abs=0.02)


def test_calibracao_ignora_taxa_extrema(base_tratada):
    treino = _dados_treino(base_tratada)
    if treino["SAIU"].nunique() < 2:
        pytest.skip("dados insuficientes")
    modelo = mr.ModeloRisco().fit(treino, treino["SAIU"])
    antes = modelo.pesos[0]
    modelo.calibrar_intercepto(treino, 0.0)  # inválido: deve ser ignorado
    assert modelo.pesos[0] == antes


def test_intercepto_negativo_treina_em_base_com_imbalance():
    """Sanidade com classe rara: 5% de positivos."""
    rng = np.random.default_rng(1)
    n = 300
    df = pd.DataFrame({"x": rng.normal(size=n)})
    y = (rng.random(n) < 0.05).astype(float)
    modelo = mr.ModeloRisco().fit(df, y)
    prob = modelo.predict_proba(df)
    assert ((prob >= 0) & (prob <= 1)).all()
    assert prob.mean() < 0.5


# ------------------------------------------------ orquestração

def test_analisar_retorna_todas_as_chaves(base_tratada):
    resultado = mr.analisar(base_tratada)
    assert set(resultado) == {"dataset", "metricas", "validacao", "coeficientes",
                             "calibracao", "scores"}


def test_analisar_com_base_insuficiente():
    reduzida = pd.DataFrame({
        "REFERENCIA": [202601, 202601],
        "REFERENCIA_LABEL": ["Jan/2026", "Jan/2026"],
        "NUMTELEFONE_STR": ["1", "2"],
        "CLIENTE": ["A", "B"], "CNPJ_FORMATADO": ["x", "y"], "UF": ["PE", "PE"],
        "TEMPO_SUSPENSAO": [10, 20], "QT_DIAS": [100, 200],
        "AGING_LIMPO": ["Até 30 dias", "Até 30 dias"], "STATUS": ["INADIMPLENTE"] * 2,
        "DTPRIMEIRAATIVACAO": pd.to_datetime(["2025-01-01"] * 2),
    })
    resultado = mr.analisar(reduzida)
    assert resultado["metricas"]["motivo"] is not None
    assert resultado["scores"].empty


def test_sem_vazamento_de_meses_futuros(base_tratada):
    """Regressão: features que usam meses futuros dariam AUC ~0,96 (vazamento).

    Um modelo honesto nesta base fica bem abaixo disso.
    """
    resultado = mr.analisar(base_tratada)
    auc_cv = resultado["metricas"]["auc_cv"]
    if auc_cv is None:
        pytest.skip("sem validação cruzada disponível")
    assert auc_cv < 0.80, (
        f"AUC(CV)={auc_cv:.3f} é alta demais para esta base — suspeite de vazamento "
        "de informação futura nas features de histórico."
    )
    assert auc_cv > 0.50, "o modelo não deveria ser pior que aleatório"


def test_metricas_do_modelo_sao_validas(base_tratada):
    met = mr.analisar(base_tratada)["metricas"]
    assert met["motivo"] is None
    assert 0.0 <= met["auc_holdout"] <= 1.0
    assert 0.0 <= met["taxa_base"] <= 1.0
    assert 0.0 <= met["taxa_esperada_alvo"] <= 1.0
    assert met["n_rotulados"] > 0
    assert met["n_features"] > 0


def test_calibracao_por_tercil_e_monotonica(base_tratada):
    """O tercil de maior prioridade deve apresentar a maior taxa de saída."""
    calibracao = mr.analisar(base_tratada)["calibracao"]
    if len(calibracao) < 2:
        pytest.skip("calibração indisponível")
    taxas = list(calibracao["TAXA_OBSERVADA_%"])
    assert taxas[0] > taxas[-1], f"tercis não discriminam: {taxas}"
    assert calibracao["LINHAS"].sum() > 0


def test_scores_cobrem_o_mes_mais_recente_e_tem_faixas(base_tratada):
    resultado = mr.analisar(base_tratada)
    scores = resultado["scores"]
    if scores.empty:
        pytest.skip("sem scores disponíveis")

    ultimo = base_tratada["REFERENCIA"].max()
    esperado = base_tratada.loc[base_tratada["REFERENCIA"] == ultimo, "NUMTELEFONE_STR"]
    assert scores["NUMTELEFONE_STR"].nunique() == esperado.nunique()
    assert set(scores["FAIXA_PROPENSAO"]) <= set(mr.ROTULOS_PROPENSAO)
    assert scores["PROB"].is_monotonic_decreasing
    assert ((scores["PROB"] >= 0) & (scores["PROB"] <= 1)).all()


def test_validacao_por_mes_tem_auc_plausivel(base_tratada):
    validacao = mr.analisar(base_tratada)["validacao"]
    if validacao.empty:
        pytest.skip("validação indisponível")
    assert validacao["AUC"].between(0.0, 1.0).all()
    assert validacao["LINHAS"].sum() > 0
