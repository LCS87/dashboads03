"""Modelo de propensão de recuperação (análise preditiva de churn por linha).

Objetivo
--------
Estimar, para cada linha **atualmente suspensa**, a probabilidade de ela **sair do
parque suspenso no mês seguinte** — o melhor indicador objetivo de reativação
(pagamento) disponível nos dados. Na prática, responde:

    "Quais linhas têm maior chance de resolver e, portanto, devem ser
     acionadas primeiro?"

Isso transforma o aging (que olha só o passado) em uma fila de trabalho priorizada.

Abordagem
---------
- **Rótulo** (`SAIU`): 1 quando a linha aparece no mês M e **não** aparece em M+1;
  0 quando permanece suspensa. É a única verdade observável na base.
- **Features** (apenas informação conhecida no mês M): `TEMPO_SUSPENSAO`,
  `DIAS_DESDE_ATIVACAO`, `MESES_CONSECUTIVOS`, `AGING_LIMPO` e `STATUS`.
  `QT_DIAS` e `APARICOES_TOTAIS` são calculados para auditoria mas ficam de fora
  por serem quase duplicatas de outras features (r ≈ 0,97–0,99).
- **Validação**: cruzada *leave-one-month-out* (métrica principal, usa todo o dado
  como teste) + holdout temporal (último mês) para a tabela de calibração.
- **Modelo**: regressão logística com regularização L2 (`L2_PADRAO`), implementada
  em **NumPy puro** — `scipy`/`scikit-learn` não são dependências do projeto.
  Convergência por Newton-Raphson (IRLS), em < 10 iterações.
- **Calibração de intercepto**: as probabilidades são reescalonadas para que a média
  coincida com a taxa de saída do mês rotulado mais recente. Corrige a superconfiança
  típica de amostras pequenas sem alterar a ordenação.
- **Prioridade**: as faixas Alta/Média/Baixa são **tercis** da própria pontuação
  (prioridade relativa), não limiares absolutos — necessário porque a taxa de saída
  mensal oscila entre ~23% e ~76%.
- **Interpretabilidade**: coeficientes padronizados indicam o peso de cada fator.

Desempenho medido nesta base (Jan–Mai/2026, 1.589 linhas rotuladas)
------------------------------------------------------------------
- AUC em validação cruzada: **≈ 0,57**; AUC no holdout (Abr/2026): **≈ 0,65**.
- No holdout, o tercil de maior propensão teve **35,9%** de saída contra **11,8%**
  no menor — **lift de 1,58×** sobre a média do mês.
- Leitura correta: o modelo serve para **ordenar a fila de acionamento**, não para
  afirmar probabilidades individuais precisas.

Limitações (honestidade estatística)
------------------------------------
- A base cobre poucos meses (5), então o conjunto de treino é pequeno e as métricas
  devem ser lidas como **ordem de priorização**, não como probabilidade calibrada.
- "Saiu do parque" é um *proxy* de recuperação: pode incluir cancelamento definitivo.
- A taxa de saída mensal é volátil e não é previsível pelas features da linha — só a
  **ordenação relativa** se mostrou estável.
- A amostra é fortemente concentrada em uma região/UF, o que limita a generalização
  geográfica.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from logging_config import get_logger

log = get_logger("modelo")

# Faixas de prioridade (por tercis da própria pontuação — prioridade *relativa*).
# Não usamos limiares absolutos porque a taxa de saída mensal desta base oscila
# entre ~23% e ~76%: um corte fixo em 0,60 deixaria o mês inteiro em "Baixa".
ROTULOS_PROPENSAO = ["Alta (Prioridade)", "Média", "Baixa"]

COLUNAS_NUMERICAS = [
    "TEMPO_SUSPENSAO",
    "DIAS_DESDE_ATIVACAO",
    "MESES_CONSECUTIVOS",
]

# `QT_DIAS` e `APARICOES_TOTAIS` existem no dataset montado (auditoria), mas **não**
# entram como features: são quase duplicatas de `DIAS_DESDE_ATIVACAO` (r≈0,99) e
# `MESES_CONSECUTIVOS` (r≈0,97). Manter pares colineares deixa os coeficientes
# instáveis sem ganho mensurável de AUC.
COLUNAS_CATEGORICAS = [
    "AGING_LIMPO",
    "STATUS",
]

# Regularização L2 escolhida por validação cruzada (a diferença entre 0,25 e 3,0 é
# menor que o erro-padrão de 4 folds; 1,0 fica no platô e é mais estável).
L2_PADRAO = 1.0

VALOR_DESCONHECIDO = "(desconhecido)"


# ===================== PREPARAÇÃO DOS DADOS =====================

def _sigmoide(z: np.ndarray) -> np.ndarray:
    """Sigmoide numericamente estável."""
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


def _data_referencia(referencia: int) -> pd.Timestamp:
    """Primeiro dia do mês de referência (AAAAmm)."""
    return pd.Timestamp(year=int(referencia) // 100, month=int(referencia) % 100, day=1)


def _indice_mes(referencia: int) -> int:
    """Converte AAAAmm em índice absoluto de mês (permite comparar continuidade)."""
    return (int(referencia) // 100) * 12 + (int(referencia) % 100)


def _meses_consecutivos(refs: list[int], alvo: int) -> int:
    """Quantos meses consecutivos (terminando no mês alvo) a linha aparece."""
    if alvo not in refs:
        return 0
    indice_alvo = _indice_mes(alvo)
    indices = sorted(_indice_mes(r) for r in refs if _indice_mes(r) <= indice_alvo)
    contagem = 1
    for anterior, atual in zip(indices[-2::-1], indices[::-1]):
        if atual - anterior != 1:
            break
        contagem += 1
    return contagem


def construir_dataset(df_base: pd.DataFrame) -> pd.DataFrame:
    """Monta o conjunto supervisionado (uma linha por par mês × linha suspensa).

    Features usam **apenas** informação disponível até o mês de referência.
    A coluna `SAIU` é o rótulo; fica nula no último mês (sem mês seguinte).

    Returns:
        DataFrame com as colunas de features, identificação e `SAIU`.
    """
    if df_base is None or df_base.empty:
        return pd.DataFrame()

    colunas_base = ["REFERENCIA", "REFERENCIA_LABEL", "NUMTELEFONE_STR", "CLIENTE",
                    "CNPJ_FORMATADO", "UF", "TEMPO_SUSPENSAO", "QT_DIAS",
                    *COLUNAS_CATEGORICAS]
    base = df_base[[c for c in colunas_base if c in df_base.columns]].copy()
    base["NUMTELEFONE_STR"] = base["NUMTELEFONE_STR"].astype(str)
    base = base.drop_duplicates(subset=["REFERENCIA", "NUMTELEFONE_STR"])

    meses = sorted(base["REFERENCIA"].unique())

    # --- Histórico por linha (APENAS meses até o mês de referência — sem vazamento)
    presenca = {
        telefone: sorted({int(r) for r in refs})
        for telefone, refs in base.groupby("NUMTELEFONE_STR")["REFERENCIA"]
    }
    base["MESES_CONSECUTIVOS"] = [
        _meses_consecutivos(presenca.get(tel, []), int(ref))
        for tel, ref in zip(base["NUMTELEFONE_STR"], base["REFERENCIA"])
    ]
    base["APARICOES_TOTAIS"] = [
        sum(1 for r in presenca.get(tel, []) if _indice_mes(r) <= _indice_mes(ref))
        for tel, ref in zip(base["NUMTELEFONE_STR"], base["REFERENCIA"])
    ]

    # --- Tenure: dias entre a ativação e o mês de referência
    if "DTPRIMEIRAATIVACAO" in df_base.columns:
        ativacao = (
            df_base.drop_duplicates(subset=["REFERENCIA", "NUMTELEFONE_STR"])
            .set_index(["REFERENCIA", "NUMTELEFONE_STR"])["DTPRIMEIRAATIVACAO"]
        )
        base["DTPRIMEIRAATIVACAO"] = [
            ativacao.get((ref, tel), pd.NaT)
            for ref, tel in zip(base["REFERENCIA"], base["NUMTELEFONE_STR"])
        ]
        base["DTPRIMEIRAATIVACAO"] = pd.to_datetime(base["DTPRIMEIRAATIVACAO"], errors="coerce")
    else:
        base["DTPRIMEIRAATIVACAO"] = pd.NaT

    base["DIAS_DESDE_ATIVACAO"] = (
        base["REFERENCIA"].apply(_data_referencia) - base["DTPRIMEIRAATIVACAO"]
    ).dt.days

    # --- Rótulo: a linha está no mês seguinte?
    proximo_mes = {meses[i]: meses[i + 1] for i in range(len(meses) - 1)}
    presentes_por_mes = {
        ref: set(base.loc[base["REFERENCIA"] == ref, "NUMTELEFONE_STR"]) for ref in meses
    }

    def _rotulo(linha: pd.Series) -> float:
        ref = int(linha["REFERENCIA"])
        if ref not in proximo_mes:
            return np.nan
        return 0.0 if linha["NUMTELEFONE_STR"] in presentes_por_mes[proximo_mes[ref]] else 1.0

    base["SAIU"] = base.apply(_rotulo, axis=1)

    return base.drop(columns=["DTPRIMEIRAATIVACAO"]).reset_index(drop=True)


# ===================== MODELO =====================

class ModeloRisco:
    """Regressão logística com L2 treinada por Newton-Raphson (IRLS).

    Attributes:
        colunas_numericas: features contínuas (padronizadas internamente).
        colunas_categoricas: features categóricas (one-hot).
    """

    def __init__(self, colunas_numericas: list[str] | None = None,
                 colunas_categoricas: list[str] | None = None,
                 l2: float = 1.0, max_iter: int = 40, tol: float = 1e-6) -> None:
        self.colunas_numericas = colunas_numericas or COLUNAS_NUMERICAS
        self.colunas_categoricas = colunas_categoricas or COLUNAS_CATEGORICAS
        self.l2 = l2
        self.max_iter = max_iter
        self.tol = tol
        self.pesos: np.ndarray | None = None
        self.nomes_features: list[str] = []
        self._medias: pd.Series | None = None
        self._desvios: pd.Series | None = None
        self._categorias: dict[str, list[str]] = {}
        self.n_iter_ = 0
        self.historico_logloss_: list[float] = []

    # ---------- engenharia de features ----------

    def _matriz(self, df: pd.DataFrame, ajustar: bool = False) -> np.ndarray:
        """Constrói a matriz de desenho [1 | numéricas padronizadas | one-hot]."""
        numericas = df.reindex(columns=self.colunas_numericas).apply(pd.to_numeric, errors="coerce")
        numericas = numericas.fillna(numericas.median() if ajustar else self._medias).fillna(0.0)

        if ajustar:
            self._medias = numericas.median()
            desvios = numericas.std(ddof=0).replace(0, 1.0)
            self._desvios = desvios
        padronizadas = (numericas - self._medias) / self._desvios

        blocos = [np.ones((len(df), 1))]
        nomes = ["intercepto"]
        for coluna in self.colunas_numericas:
            blocos.append(padronizadas[coluna].to_numpy().reshape(-1, 1))
            nomes.append(coluna)

        for coluna in self.colunas_categoricas:
            if coluna in df.columns:
                serie = df[coluna].astype("object").fillna(VALOR_DESCONHECIDO).astype(str)
            else:
                # Coluna ausente no lote: trata tudo como "(desconhecido)" em vez de quebrar
                serie = pd.Series([VALOR_DESCONHECIDO] * len(df), index=df.index)
            if ajustar:
                self._categorias[coluna] = sorted(serie.unique())[:-1]  # última = referência
            for nivel in self._categorias.get(coluna, []):
                blocos.append((serie == nivel).to_numpy().astype(float).reshape(-1, 1))
                nomes.append(f"{coluna}={nivel}")

        if ajustar:
            self.nomes_features = nomes
        return np.hstack(blocos)

    # ---------- treino ----------

    def fit(self, df: pd.DataFrame, y: pd.Series | np.ndarray) -> "ModeloRisco":
        """Treina o modelo por Newton-Raphson com regularização L2."""
        X = self._matriz(df, ajustar=True)
        alvo = np.asarray(y, dtype=float)
        pesos = np.zeros(X.shape[1])
        regularizador = np.ones(X.shape[1]) * self.l2
        regularizador[0] = 0.0  # não regulariza o intercepto

        for iteracao in range(self.max_iter):
            prob = _sigmoide(X @ pesos)
            gradiente = X.T @ (prob - alvo) + regularizador * pesos
            hessiana = X.T @ (X * (prob * (1 - prob))[:, None]) + np.diag(regularizador)
            try:
                passo = np.linalg.solve(hessiana, gradiente)
            except np.linalg.LinAlgError:
                passo = np.linalg.lstsq(hessiana, gradiente, rcond=None)[0]

            pesos = pesos - passo
            logloss = -np.mean(
                alvo * np.log(np.clip(prob, 1e-12, 1)) +
                (1 - alvo) * np.log(np.clip(1 - prob, 1e-12, 1))
            )
            self.historico_logloss_.append(float(logloss))
            self.n_iter_ = iteracao + 1
            if np.max(np.abs(passo)) < self.tol:
                break

        self.pesos = pesos
        return self

    # ---------- inferência ----------

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Probabilidade estimada de a linha sair do parque no mês seguinte."""
        if self.pesos is None:
            raise RuntimeError("Modelo não treinado: chame fit() antes de prever.")
        return _sigmoide(self._matriz(df, ajustar=False) @ self.pesos)

    def calibrar_intercepto(self, df: pd.DataFrame, taxa_alvo: float) -> "ModeloRisco":
        """Reajusta o intercepto para que a probabilidade média iguale `taxa_alvo`.

        Corrige a superconfiança típica de amostras pequenas: a *ordenação* (o que
        importa para priorizar) é preservada, mas as magnitudes passam a refletir a
        taxa de saída mais recente observada. Resolvido por bisseção, pois a média
        da sigmoide é monotônica no intercepto.

        Args:
            df: conjunto usado como referência (a base a ser pontuada).
            taxa_alvo: taxa de saída esperada (0–1), típicamente a do mês mais recente.
        """
        if self.pesos is None:
            raise RuntimeError("Modelo não treinado: chame fit() antes de calibrar.")
        if not 0.0 < taxa_alvo < 1.0:
            return self

        X = self._matriz(df, ajustar=False)
        parte_fixa = X[:, 1:] @ self.pesos[1:]

        limite_inferior, limite_superior = -60.0, 60.0
        for _ in range(200):
            meio = (limite_inferior + limite_superior) / 2.0
            if _sigmoide(parte_fixa + meio).mean() < taxa_alvo:
                limite_inferior = meio
            else:
                limite_superior = meio

        self.pesos[0] = (limite_inferior + limite_superior) / 2.0
        return self

    def coeficientes(self) -> pd.DataFrame:
        """Pesos padronizados por feature, ordenados por importância absoluta."""
        if self.pesos is None:
            return pd.DataFrame(columns=["FEATURE", "PESO", "EFEITO"])
        tabela = pd.DataFrame({"FEATURE": self.nomes_features, "PESO": self.pesos})
        tabela = tabela[tabela["FEATURE"] != "intercepto"].copy()
        tabela["EFEITO"] = np.where(tabela["PESO"] > 0, "aumenta a saída", "reduz a saída")
        return (
            tabela.reindex(tabela["PESO"].abs().sort_values(ascending=False).index)
            .reset_index(drop=True)
        )


# ===================== AVALIAÇÃO =====================

def auc(y: np.ndarray, prob: np.ndarray) -> float | None:
    """Área sob a curva ROC (0,5 = aleatório; 1,0 = perfeito), com empates tratados.

    Implementada pela estatística U de Mann-Whitney: equivale à probabilidade de o
    modelo dar score maior a um caso positivo do que a um negativo.
    """
    y = np.asarray(y, dtype=float)
    prob = np.asarray(prob, dtype=float)
    positivos = int((y == 1).sum())
    negativos = int((y == 0).sum())
    if positivos == 0 or negativos == 0:
        return None

    # np.unique devolve valores crescentes: o grupo k ocupa as posições
    # [inicio[k], fim[k]] no ranking. Empates recebem o rank médio do grupo.
    _, inverso, contagens = np.unique(prob, return_inverse=True, return_counts=True)
    fim = np.cumsum(contagens).astype(float)
    inicio = fim - contagens + 1.0
    ranks = ((inicio + fim) / 2.0)[inverso]

    return float((ranks[y == 1].sum() - positivos * (positivos + 1) / 2) / (positivos * negativos))


def faixas_por_tercis(probabilidades: np.ndarray | pd.Series) -> np.ndarray:
    """Classifica a pontuação em tercis de prioridade (Alta / Média / Baixa).

    Garante uma fila de trabalho utilizável independentemente do nível absoluto das
    probabilidades: a Alta recebe ~1/3 das linhas com maior score, a Baixa ~1/3 com
    o menor. É prioridade **relativa**, não probabilidade absoluta.
    """
    valores = np.asarray(probabilidades, dtype=float)
    if valores.size == 0:
        return np.array([], dtype=object)
    if valores.size < 3:
        return np.array(["Alta (Prioridade)"] * valores.size, dtype=object)

    corte_alto = np.quantile(valores, 2 / 3)
    corte_baixo = np.quantile(valores, 1 / 3)
    return np.where(
        valores >= corte_alto, "Alta (Prioridade)",
        np.where(valores >= corte_baixo, "Média", "Baixa"),
    ).astype(object)


def validar_cruzado(rotulado: pd.DataFrame, l2: float = L2_PADRAO) -> pd.DataFrame:
    """Validação cruzada *leave-one-month-out*: um mês de teste, os outros de treino.

    É a avaliação mais honesta possível com 4 transições: usa todo o dado como teste
    uma vez e nunca treina no futuro do mês avaliado.

    Returns:
        DataFrame com `REFERENCIA_LABEL`, `LINHAS`, `TAXA_SAIDA_%` e `AUC` por mês.
    """
    registros = []
    for alvo in sorted(rotulado["REFERENCIA"].unique()):
        treino = rotulado[rotulado["REFERENCIA"] != alvo]
        teste = rotulado[rotulado["REFERENCIA"] == alvo]
        if treino["SAIU"].nunique() < 2 or teste["SAIU"].nunique() < 2:
            continue
        modelo = ModeloRisco(l2=l2).fit(treino, treino["SAIU"])
        # O AUC é invariante a reescalonamento monotônico, então não é preciso
        # calibrar o intercepto aqui — a calibração é feita no holdout/score.
        registros.append({
            "REFERENCIA_LABEL": teste["REFERENCIA_LABEL"].iloc[0],
            "LINHAS": len(teste),
            "TAXA_SAIDA_%": round(float(teste["SAIU"].mean()) * 100, 1),
            "AUC": round(float(auc(teste["SAIU"].to_numpy(), modelo.predict_proba(teste))), 3),
        })
    return pd.DataFrame(registros, columns=["REFERENCIA_LABEL", "LINHAS", "TAXA_SAIDA_%", "AUC"])


# ===================== ORQUESTRAÇÃO =====================

def analisar(df_base: pd.DataFrame, l2: float = L2_PADRAO) -> dict:
    """Treina, valida (CV + holdout) e aplica o modelo ao mês mais recente da base.

    Returns:
        dict com `dataset`, `metricas`, `validacao`, `coeficientes`, `calibracao`
        e `scores`. Todas as chaves existem; com dados insuficientes, `metricas`
        traz `motivo` e as demais vêm vazias.
    """
    vazio = {
        "dataset": pd.DataFrame(),
        "metricas": {"motivo": "Base insuficiente para treinar o modelo (mínimo 3 meses)."},
        "validacao": pd.DataFrame(),
        "coeficientes": pd.DataFrame(),
        "calibracao": pd.DataFrame(),
        "scores": pd.DataFrame(),
    }
    dataset = construir_dataset(df_base)
    if dataset.empty:
        return vazio

    rotulado = dataset[dataset["SAIU"].notna()].copy()
    meses = sorted(rotulado["REFERENCIA"].unique())
    if len(meses) < 3:
        return vazio

    # ---------- Validação cruzada leave-one-month-out (métrica principal) ----------
    validacao = validar_cruzado(rotulado, l2=l2)
    auc_cv = float(validacao["AUC"].mean()) if not validacao.empty else None

    # ---------- Holdout temporal: treina até o penúltimo mês, testa no último ----------
    treino = rotulado[rotulado["REFERENCIA"].isin(meses[:-1])]
    teste = rotulado[rotulado["REFERENCIA"] == meses[-1]]
    modelo_holdout = ModeloRisco(l2=l2).fit(treino, treino["SAIU"])
    taxa_treino_recente = float(
        treino.loc[treino["REFERENCIA"] == treino["REFERENCIA"].max(), "SAIU"].mean()
    )
    modelo_holdout.calibrar_intercepto(teste, taxa_treino_recente)
    prob_teste = modelo_holdout.predict_proba(teste)

    taxa_base = float(teste["SAIU"].mean())
    baseline_acuracia = max(taxa_base, 1 - taxa_base)
    acuracia = float(((prob_teste >= 0.5).astype(float) == teste["SAIU"].to_numpy()).mean())

    metricas = {
        "n_treino": int(len(treino)),
        "n_teste": int(len(teste)),
        "n_rotulados": int(len(rotulado)),
        "n_features": int(len(modelo_holdout.nomes_features) - 1),
        "auc_cv": auc_cv,
        "auc_cv_min": float(validacao["AUC"].min()) if not validacao.empty else None,
        "auc_cv_max": float(validacao["AUC"].max()) if not validacao.empty else None,
        "auc_holdout": auc(teste["SAIU"].to_numpy(), prob_teste),
        "acuracia": acuracia,
        "acuracia_baseline": baseline_acuracia,
        "taxa_base": taxa_base,
        "taxa_calibracao_holdout": taxa_treino_recente,
        "mes_teste": int(meses[-1]),
        "iteracoes": modelo_holdout.n_iter_,
        "motivo": None,
    }

    # ---------- Calibração no holdout: taxa observada por tercil de propensão ----------
    calibracao = pd.DataFrame({"PROB": prob_teste, "SAIU": teste["SAIU"].to_numpy()})
    calibracao["FAIXA_PROPENSAO"] = faixas_por_tercis(calibracao["PROB"].to_numpy())
    calibracao = (
        calibracao.groupby("FAIXA_PROPENSAO")
        .agg(LINHAS=("SAIU", "size"), SAIRAM=("SAIU", "sum"), PROB_MEDIA=("PROB", "mean"))
        .reset_index()
    )
    calibracao["TAXA_OBSERVADA_%"] = (calibracao["SAIRAM"] / calibracao["LINHAS"] * 100).round(1)
    calibracao["PROB_MEDIA_%"] = (calibracao["PROB_MEDIA"] * 100).round(1)
    taxa_geral = float(teste["SAIU"].mean()) * 100
    calibracao["LIFT"] = (
        (calibracao["TAXA_OBSERVADA_%"] / taxa_geral) if taxa_geral > 0 else 0.0
    ).round(2)
    ordem_faixas = {rotulo: i for i, rotulo in enumerate(ROTULOS_PROPENSAO)}
    calibracao["_ordem"] = calibracao["FAIXA_PROPENSAO"].map(ordem_faixas).fillna(99)
    calibracao = (
        calibracao.sort_values("_ordem")
        .drop(columns=["PROB_MEDIA", "_ordem"])
        .reset_index(drop=True)
    )
    calibracao = calibracao[
        ["FAIXA_PROPENSAO", "LINHAS", "SAIRAM", "TAXA_OBSERVADA_%", "LIFT", "PROB_MEDIA_%"]
    ]

    # ---------- Modelo final (todo o histórico) + pontuação do mês mais recente ----------
    modelo_final = ModeloRisco(l2=l2).fit(rotulado, rotulado["SAIU"])
    ultimo_mes = max(dataset["REFERENCIA"].unique())
    alvo = dataset[dataset["REFERENCIA"] == ultimo_mes].copy()

    # Taxa de saída do mês rotulado mais recente = melhor estimativa para o mês alvo
    taxa_esperada = float(rotulado.loc[rotulado["REFERENCIA"] == meses[-1], "SAIU"].mean())
    modelo_final.calibrar_intercepto(alvo, taxa_esperada)
    metricas["taxa_esperada_alvo"] = taxa_esperada
    metricas["mes_referencia_taxa"] = int(meses[-1])

    alvo["PROB"] = modelo_final.predict_proba(alvo)
    alvo["FAIXA_PROPENSAO"] = faixas_por_tercis(alvo["PROB"].to_numpy())
    scores = (
        alvo.sort_values("PROB", ascending=False)
        .reset_index(drop=True)
        [["REFERENCIA_LABEL", "NUMTELEFONE_STR", "CLIENTE", "CNPJ_FORMATADO", "UF",
          "AGING_LIMPO", "TEMPO_SUSPENSAO", "MESES_CONSECUTIVOS", "PROB", "FAIXA_PROPENSAO"]]
    )

    log.info(
        "Modelo de propensão | rotulados=%d | AUC(CV)=%s | AUC(holdout=%s)=%s | mês alvo=%s",
        len(rotulado),
        f"{auc_cv:.3f}" if auc_cv is not None else "n/d",
        metricas["mes_teste"],
        f"{metricas['auc_holdout']:.3f}" if metricas["auc_holdout"] is not None else "n/d",
        int(ultimo_mes),
    )

    return {
        "dataset": dataset,
        "metricas": metricas,
        "validacao": validacao,
        "coeficientes": modelo_final.coeficientes(),
        "calibracao": calibracao,
        "scores": scores,
    }
