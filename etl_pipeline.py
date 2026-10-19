import os
import pandas as pd

from logging_config import configurar_logging, mascarar

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log = configurar_logging("etl")

# Dicionário oficial de DDD para UF
DDD_TO_UF = {
    # Nordeste
    "81": "PE", "87": "PE",
    "82": "AL",
    "83": "PB",
    "84": "RN",
    "85": "CE", "88": "CE",
    "86": "PI", "89": "PI",
    "98": "MA", "99": "MA",
    "79": "SE",
    "71": "BA", "73": "BA", "74": "BA", "75": "BA", "77": "BA",
    # Sudeste
    "11": "SP", "12": "SP", "13": "SP", "14": "SP", "15": "SP", "16": "SP", "17": "SP", "18": "SP", "19": "SP",
    "21": "RJ", "22": "RJ", "24": "RJ",
    "27": "ES", "28": "ES",
    "31": "MG", "32": "MG", "33": "MG", "34": "MG", "35": "MG", "37": "MG", "38": "MG",
    # Sul
    "41": "PR", "42": "PR", "43": "PR", "44": "PR", "45": "PR", "46": "PR",
    "47": "SC", "48": "SC", "49": "SC",
    "51": "RS", "53": "RS", "54": "RS", "55": "RS",
    # Centro-Oeste / Norte
    "61": "DF", "62": "GO", "64": "GO", "63": "TO", "65": "MT", "66": "MT", "67": "MS",
    "68": "AC", "69": "RO", "91": "PA", "92": "AM", "95": "RR", "96": "AP", "97": "AM"
}

UF_TO_REGION = {
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste",
    "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "SP": "Sudeste", "RJ": "Sudeste", "MG": "Sudeste", "ES": "Sudeste",
    "PR": "Sul", "SC": "Sul", "RS": "Sul",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "AM": "Norte", "PA": "Norte", "AC": "Norte", "RO": "Norte", "RR": "Norte", "AP": "Norte", "TO": "Norte"
}

MONTH_NAME_TO_NUM = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
}
MONTH_NUM_TO_ABBR = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai",
    6: "Jun", 7: "Jul", 8: "Ago", 9: "Set",
    10: "Out", 11: "Nov", 12: "Dez"
}

# Colunas de identificadores corporativos removidas por política de anonimização
ANONIMIZAR_DROP = ["DEALEAR", "CD_DEALER", "NOME_DIRETOR", "NOME_DIVISAO"]

# Remoção de registros 100% idênticos antes do tratamento.
# Motivo: o arquivo consolidado trazia o mês de Abr/2026 carregado 3x (1.010 linhas
# repetidas), o que inflava artificialmente o pico de volume do período.
# Defina como False para preservar a base como veio do arquivo de origem.
REMOVER_DUPLICATAS_EXATAS = True

# Consistência da extração por bloco mensal.
#
# A coluna TEMPO_SUSPENSAO do arquivo de origem é calculada na data em que o mês foi
# extraído, o que é recuperável com exatidão:  DT_SUSPENSAO + TEMPO_SUSPENSAO  é
# constante dentro de cada mês e revela a data da extração. Se essa data se afastar
# demais do mês de referência, o bloco está com o aging em escala diferente — foi o
# caso de Abr/2026, extraído em 22/06/2026 (ver ANALISE_E_PLANO_DE_MELHORIAS.md).
#
# Tolerância, em dias, entre o 1º dia do mês de referência e a extração implícita.
TOLERANCIA_EXTRACAO_DIAS = 45

# Quando True, o ETL **recalcula** o aging a partir de DT_SUSPENSAO e do mês de
# referência, tornando os meses comparáveis (corrige o bloco inconsistente acima).
# Desligado por padrão porque altera um indicador de negócio — ative com consciência.
NORMALIZAR_AGING_POR_REFERENCIA = False

# Colunas esperadas em qualquer base de entrada do parque suspenso
COLUNAS_OBRIGATORIAS = [
    "CNPJ_CLIENTE", "CLIENTE", "MATERIAL", "AGING", "STATUS", "UF",
    "NUMTELEFONE", "DTPRIMEIRAATIVACAO", "DT_SUSPENSAO",
    "QT_DIAS", "TEMPO_SUSPENSAO", "TP_SUSPENSAO", "REFERENCIA",
]

# Colunas derivadas que devem existir ao final do pipeline
COLUNAS_DERIVADAS = [
    "NUMTELEFONE_STR", "DDD", "REGIAO", "AGING_LIMPO", "AGING_ORDEM",
    "FAIXA_RISCO", "REFERENCIA_LABEL", "CNPJ_FORMATADO", "MSG_COBRANCA",
]

REFERENCIA_MIN, REFERENCIA_MAX = 200001, 210012
DATA_MINIMA_ATIVACAO = "2010-01-01"


class ETLValidationError(Exception):
    """Erro fatal de validação da base de entrada (interrompe o pipeline)."""


def validar_base(df: pd.DataFrame, origem: str = "base",
                 obrigatorias: list[str] | None = None,
                 estrito: bool = True) -> dict:
    """Valida integridade, formato e consistência da base antes/depois do ETL.

    Problemas fatais (estrutura) lançam ETLValidationError quando `estrito=True`.
    Problemas de qualidade (nulos, datas fora de faixa, duplicatas) são registrados
    como avisos e devolvidos no resumo para auditoria.

    Returns:
        dict com o resumo da validação (linhas, colunas, alertas).
    """
    obrigatorias = obrigatorias or COLUNAS_OBRIGATORIAS
    resumo = {"origem": origem, "linhas": 0, "colunas_faltantes": [], "alertas": []}

    # --- Fatais: base vazia / não é DataFrame ---
    if df is None or not isinstance(df, pd.DataFrame):
        raise ETLValidationError(f"[{origem}] Base inválida ou inexistente (não é DataFrame).")
    if df.empty:
        raise ETLValidationError(f"[{origem}] Base vazia: nenhuma linha para processar.")

    resumo["linhas"] = len(df)

    # --- Fatais: colunas obrigatórias ausentes ---
    faltantes = [c for c in obrigatorias if c not in df.columns]
    resumo["colunas_faltantes"] = faltantes
    if faltantes:
        msg = (f"[{origem}] Colunas obrigatórias ausentes: {faltantes}. "
               f"Colunas encontradas: {list(df.columns)[:15]}...")
        if estrito:
            raise ETLValidationError(msg)
        resumo["alertas"].append(msg)

    # --- REFERENCIA: numérica e dentro da faixa esperada ---
    if "REFERENCIA" in df.columns:
        refs_num = pd.to_numeric(df["REFERENCIA"], errors="coerce")
        qtd_ref_invalida = int(refs_num.isna().sum())
        if qtd_ref_invalida:
            resumo["alertas"].append(f"REFERENCIA não numérica em {qtd_ref_invalida} linha(s).")
        refs_validas = refs_num.dropna().astype(int)
        fora_faixa = refs_validas[(refs_validas < REFERENCIA_MIN) | (refs_validas > REFERENCIA_MAX)]
        if len(fora_faixa):
            resumo["alertas"].append(f"REFERENCIA fora da faixa AAAAmm em {len(fora_faixa)} linha(s).")
        if refs_validas.empty and estrito:
            raise ETLValidationError(f"[{origem}] Nenhuma REFERENCIA válida encontrada.")
        resumo["meses"] = sorted(refs_validas.unique().tolist())

    # --- Telefone ---
    if "NUMTELEFONE" in df.columns:
        qtd_tel_nulo = int(df["NUMTELEFONE"].isna().sum())
        if qtd_tel_nulo:
            resumo["alertas"].append(f"{qtd_tel_nulo} linha(s) sem NUMTELEFONE.")
        digitos = df["NUMTELEFONE"].astype(str).str.replace(r"\D", "", regex=True)
        qtd_ddd_curto = int((digitos.str.len() < 10).sum())
        if qtd_ddd_curto:
            resumo["alertas"].append(f"{qtd_ddd_curto} linha(s) com telefone curto (<10 dígitos).")

    # --- Datas ---
    hoje = pd.Timestamp.now().normalize()
    for col in ["DT_SUSPENSAO", "DTPRIMEIRAATIVACAO"]:
        if col in df.columns:
            datas = pd.to_datetime(df[col], errors="coerce")
            qtd_invalidas = int(datas.isna().sum())
            if qtd_invalidas:
                resumo["alertas"].append(f"{col}: {qtd_invalidas} data(s) inválida(s) ou vazia(s).")
            futuras = int((datas > hoje).sum())
            if futuras:
                resumo["alertas"].append(f"{col}: {futuras} data(s) no futuro.")
            if col == "DTPRIMEIRAATIVACAO":
                antigas = int((datas < pd.Timestamp(DATA_MINIMA_ATIVACAO)).sum())
                if antigas:
                    resumo["alertas"].append(f"{col}: {antigas} data(s) anterior(es) a {DATA_MINIMA_ATIVACAO}.")

    # --- CNPJ ---
    if "CNPJ_CLIENTE" in df.columns:
        qtd_cnpj_nulo = int(df["CNPJ_CLIENTE"].isna().sum())
        if qtd_cnpj_nulo:
            resumo["alertas"].append(f"{qtd_cnpj_nulo} linha(s) sem CNPJ_CLIENTE.")

    # --- Duplicatas (qualidade, não fatal) ---
    qtd_dup_exatas = int(df.duplicated().sum())
    if qtd_dup_exatas:
        # Detalha por mês, pois a duplicação costuma estar concentrada em uma carga
        if "REFERENCIA" in df.columns:
            dup_por_mes = (
                df.groupby("REFERENCIA", group_keys=False)
                .apply(lambda g: int(g.duplicated().sum()))
            )
            dup_por_mes = dup_por_mes[dup_por_mes > 0]
            detalhe = ", ".join(
                f"{ref_to_label(ref)}: {qtd}" for ref, qtd in dup_por_mes.items()
            )
        else:
            detalhe = "detalhamento indisponível"
        resumo["alertas"].append(
            f"{qtd_dup_exatas} registro(s) 100% idêntico(s) — provável carga duplicada do arquivo de origem ({detalhe})."
        )

    # --- Consistência da data de extração por bloco mensal (qualidade) ---
    if {"REFERENCIA", "DT_SUSPENSAO", "TEMPO_SUSPENSAO"}.issubset(df.columns):
        extracoes = extracoes_por_mes(df)
        resumo["extracoes"] = extracoes.to_dict("records")
        inconsistentes = extracoes[~extracoes["CONSISTENTE"]]
        if len(inconsistentes):
            detalhe = ", ".join(
                descrever_extracao(linha) for _, linha in inconsistentes.iterrows()
            )
            resumo["alertas"].append(
                "Bloco(s) mensal(is) com aging calculado fora do mês de referência "
                f"({detalhe}). Comparações mês a mês de aging ficam distorcidas; "
                "considere NORMALIZAR_AGING_POR_REFERENCIA=True."
            )

    # --- Log do resumo ---
    if resumo["alertas"]:
        log.warning("Validação [%s]: %d linha(s), %d alerta(s) de qualidade.", origem,
                    resumo["linhas"], len(resumo["alertas"]))
        for alerta in resumo["alertas"]:
            log.warning("  • [%s] %s", origem, alerta)
    else:
        log.info("Validação [%s]: %d linha(s), sem alertas de qualidade.", origem, resumo["linhas"])
    return resumo

# ================= CONSISTÊNCIA DA EXTRAÇÃO E NORMALIZAÇÃO DE AGING =================

def extracoes_por_mes(df: pd.DataFrame) -> pd.DataFrame:
    """Reconstrói a **data de extração** de cada bloco mensal da base.

    A coluna de origem `TEMPO_SUSPENSAO` é o número de dias entre `DT_SUSPENSAO` e a
    data em que o mês foi extraído, portanto `DT_SUSPENSAO + TEMPO_SUSPENSAO` é
    constante dentro de um mês e revela essa data com exatidão. Se ela estiver muito
    distante do mês de referência, o bloco foi calculado em outro momento (aging em
    escala diferente) — foi o caso de Abr/2026.

    Args:
        df: base (tratada ou bruta) com REFERENCIA, DT_SUSPENSAO e TEMPO_SUSPENSAO.

    Returns:
        DataFrame com `REFERENCIA`, `REFERENCIA_LABEL`, `EXTRACAO_IMPLICITA`, `LINHAS`,
        `DESVIO_DIAS` (extração − 1º dia do mês) e `CONSISTENTE` (bool).
    """
    colunas = ["REFERENCIA", "REFERENCIA_LABEL", "EXTRACAO_IMPLICITA", "LINHAS",
               "DESVIO_DIAS", "CONSISTENTE"]
    if df is None or df.empty or not {"REFERENCIA", "DT_SUSPENSAO", "TEMPO_SUSPENSAO"}.issubset(df.columns):
        return pd.DataFrame(columns=colunas)

    dados = df[["REFERENCIA", "DT_SUSPENSAO", "TEMPO_SUSPENSAO"]].copy()
    dados["DT_SUSPENSAO"] = pd.to_datetime(dados["DT_SUSPENSAO"], errors="coerce")
    dados["TEMPO_SUSPENSAO"] = pd.to_numeric(dados["TEMPO_SUSPENSAO"], errors="coerce")
    dados["EXTRACAO_IMPLICITA"] = (
        dados["DT_SUSPENSAO"] + pd.to_timedelta(dados["TEMPO_SUSPENSAO"], unit="D")
    )

    def _moda_data(serie: pd.Series) -> pd.Timestamp:
        moda = serie.dropna().mode()
        return moda.iloc[0] if not moda.empty else pd.NaT

    resumo = dados.groupby("REFERENCIA").agg(
        EXTRACAO_IMPLICITA=("EXTRACAO_IMPLICITA", _moda_data),
        LINHAS=("EXTRACAO_IMPLICITA", "size"),
    ).reset_index()
    resumo["REFERENCIA_LABEL"] = resumo["REFERENCIA"].apply(ref_to_label)
    inicio_mes = pd.to_datetime(resumo["REFERENCIA"].astype(str), format="%Y%m", errors="coerce")
    resumo["DESVIO_DIAS"] = (resumo["EXTRACAO_IMPLICITA"] - inicio_mes).dt.days
    resumo["CONSISTENTE"] = resumo["DESVIO_DIAS"].abs() <= TOLERANCIA_EXTRACAO_DIAS
    return resumo[colunas]


def descrever_extracao(linha: pd.Series) -> str:
    """Formata uma linha de `extracoes_por_mes` para log/alerta.

    Tolerante a blocos cuja data de extração não pôde ser reconstruída (mês de
    referência inválido, datas ausentes): nesses casos devolve uma descrição textual
    em vez de tentar formatar um número inexistente.
    """
    extracao = linha.get("EXTRACAO_IMPLICITA")
    desvio = linha.get("DESVIO_DIAS")
    if pd.isna(extracao) or pd.isna(desvio):
        return f"{linha['REFERENCIA_LABEL']}: data de extração indeterminada"
    return (f"{linha['REFERENCIA_LABEL']}: extração em "
            f"{pd.Timestamp(extracao).date()} ({int(desvio):+d} dias do 1º dia do mês)")


def _faixa_aging_dias(dias: float) -> str:
    """Converte dias de suspensão na faixa canônica de aging."""
    if pd.isna(dias):
        return "Não Informado"
    if dias <= 30:
        return "Até 30 dias"
    if dias <= 60:
        return "De 31 a 60 dias"
    if dias <= 90:
        return "De 61 a 90 dias"
    if dias <= 120:
        return "De 91 a 120 dias"
    return "Maior que 120 dias"


def normalizar_aging(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Recalcula `TEMPO_SUSPENSAO`/`AGING` a partir de `DT_SUSPENSAO` e do mês de referência.

    Usa a data de suspensão — o campo autoritativo — em vez da coluna pré-calculada
    pela origem, que pode ter sido gerada em outro momento (ver `extracoes_por_mes`).
    O resultado é "dias de suspensão no 1º dia do mês de referência", o que torna
    todos os meses comparáveis entre si.

    Args:
        df: base com REFERENCIA e DT_SUSPENSAO.

    Returns:
        tuple[pd.DataFrame, int]: base ajustada e quantidade de linhas ajustadas.
    """
    if df is None or df.empty or not {"REFERENCIA", "DT_SUSPENSAO"}.issubset(df.columns):
        return df, 0

    base = df.copy()
    suspensao = pd.to_datetime(base["DT_SUSPENSAO"], errors="coerce")
    inicio_mes = pd.to_datetime(
        base["REFERENCIA"].astype(str), format="%Y%m", errors="coerce"
    )
    dias = (inicio_mes - suspensao).dt.days.clip(lower=0)

    ajustadas = int((dias != pd.to_numeric(base.get("TEMPO_SUSPENSAO"), errors="coerce")).sum())
    base["TEMPO_SUSPENSAO"] = dias
    base["AGING"] = dias.apply(_faixa_aging_dias)
    return base, ajustadas


# Formato: 202601 -> "Jan/2026" (gerado dinamicamente para qualquer mês/ano)
def ref_to_label(ref: int) -> str:
    """Converte a referência numérica AAAAmm em rótulo legível (ex.: 202606 -> 'Jun/2026')."""
    ref = int(ref)
    year, month = ref // 100, ref % 100
    abbr = MONTH_NUM_TO_ABBR.get(month, str(month))
    return f"{abbr}/{year}"

def clean_aging(val: object) -> str:
    """Normaliza o rótulo de aging para a faixa canônica usada nas análises.

    Ex.: "ATÉ 30 DIAS" → "Até 30 dias". Valores nulos viram "Não Informado".
    """
    if pd.isna(val):
        return "Não Informado"
    s = str(val).upper()
    if "AT" in s and "30" in s:
        return "Até 30 dias"
    elif "31" in s and "60" in s:
        return "De 31 a 60 dias"
    elif "61" in s and "90" in s:
        return "De 61 a 90 dias"
    elif "91" in s and "120" in s:
        return "De 91 a 120 dias"
    elif "120" in s:
        return "Maior que 120 dias"
    return val

def df_read_any_csv(path: str) -> pd.DataFrame | None:
    """Leitura robusta de qualquer CSV do projeto com fallback de encoding.

    Returns:
        DataFrame lido, ou None se nenhum encoding funcionar (registrado em log).
    """
    erros = []
    for enc in ['utf-8-sig', 'latin1', 'cp1252', 'utf-8']:
        try:
            df = pd.read_csv(path, sep=';', encoding=enc)
            log.debug("Arquivo '%s' lido com encoding %s.", os.path.basename(path), enc)
            return df
        except Exception as erro:
            erros.append(f"{enc}: {erro}")
    log.error("Não foi possível ler '%s' com nenhum encoding. Detalhes: %s",
              os.path.basename(path), " | ".join(erros))
    return None

def df_clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove BOM e espaços dos nomes de colunas (normalização da base de entrada)."""
    df.columns = [c.replace('\ufeff', '').strip() for c in df.columns]
    return df

def list_monthly_files() -> list[str]:
    """Detecta arquivos de base mensal individual (ex: ParqueSuspenso_junho.csv)."""
    import glob as _glob
    pattern = os.path.join(BASE_DIR, "ParqueSuspenso_*.csv")
    return sorted(_glob.glob(pattern))

def file_reference(df: pd.DataFrame, filepath: str) -> int | None:
    """Extrai a REFERENCIA (YYYYMM) do arquivo: da própria base ou do nome do arquivo."""
    if 'REFERENCIA' in df.columns and len(df) > 0:
        try:
            return int(pd.to_numeric(df['REFERENCIA'], errors='coerce').dropna().astype(int).mode()[0])
        except Exception:
            pass
    name = os.path.basename(filepath).lower()
    name = name.replace("parquesuspenso_", "").replace(".csv", "")
    for token, num in MONTH_NAME_TO_NUM.items():
        if token in name:
            digits = ''.join(ch for ch in name if ch.isdigit())
            year = int(digits[:4]) if len(digits[:4]) == 4 else 2026
            return year * 100 + num
    return None

def ingest_new_months(df_base: pd.DataFrame) -> pd.DataFrame:
    """Detecta arquivos mensais novos (meses ainda não presentes na base consolidada)
    e os anexa ao DataFrame, garantindo ingestão automática de próximos meses."""
    if 'REFERENCIA' not in df_base.columns:
        log.warning("Ingestão automática ignorada: base consolidada sem coluna REFERENCIA.")
        return df_base, 0
    refs_existentes = set(df_base['REFERENCIA'].astype(int).unique())
    adicionados = 0
    novos_dfs = []
    for fp in list_monthly_files():
        df_m = df_read_any_csv(fp)
        if df_m is None or len(df_m) == 0:
            log.warning("Arquivo '%s' ilegível ou vazio. Ignorado.", os.path.basename(fp))
            continue
        df_m = df_clean_columns(df_m)
        ref = file_reference(df_m, fp)
        if ref is None or ref in refs_existentes:
            continue  # mês já consolidado ou não identificável
        if 'REFERENCIA' not in df_m.columns:
            df_m['REFERENCIA'] = ref
        novos_dfs.append(df_m)
        refs_existentes.add(ref)
        adicionados += len(df_m)
        log.info("Ingestão automática: %s (%s) -> %d novos registros.",
                 os.path.basename(fp), ref_to_label(ref), len(df_m))
    if novos_dfs:
        df_base = pd.concat([df_base] + [
            nd[df_base.columns.intersection(nd.columns)] for nd in novos_dfs
        ], ignore_index=True)
    return df_base, adicionados

def get_parquet_references() -> set[int]:
    """REFs já presentes no Parquet tratado (leitura leve de 1 coluna)."""
    parquet_path = os.path.join(BASE_DIR, "parque_suspenso_tratado.parquet")
    if not os.path.exists(parquet_path):
        return set()
    try:
        cols = pd.read_parquet(parquet_path, columns=['REFERENCIA'])
        return set(cols['REFERENCIA'].astype(int).unique())
    except Exception:
        try:
            cols = pd.read_parquet(parquet_path)
            return set(cols['REFERENCIA'].astype(int).unique())
        except Exception:
            return set()

def refresh_if_new_months() -> bool:
    """Verifica se há novos arquivos mensais na pasta e, se houver, reexecuta o ETL.
    Retorna True quando a base foi atualizada."""
    parquet_refs = get_parquet_references()
    if not parquet_refs:
        return False  # sem Parquet: o app cuidará da primeira carga
    refs_existentes = set()
    for fp in list_monthly_files():
        df_m = df_read_any_csv(fp)
        if df_m is None:
            continue
        ref = file_reference(df_clean_columns(df_m), fp)
        if ref is not None:
            refs_existentes.add(ref)
    faltantes = refs_existentes - parquet_refs
    if faltantes:
        # existem meses de arquivo ainda não tratados na base
        log.info("Novos meses detectados: %s. Reexecutando ETL...",
                 [ref_to_label(r) for r in sorted(faltantes)])
        run_etl()
        return True
    return False


def remover_duplicatas_exatas(df: pd.DataFrame | None) -> tuple[pd.DataFrame, int]:
    """Remove registros 100% idênticos (carga duplicada do arquivo de origem).

    A remoção só afeta linhas em que TODAS as colunas são iguais — nenhuma
    informação de negócio é perdida. O volume removido é registrado em log,
    detalhado por mês, para auditoria.

    Returns:
        tuple(DataFrame sem duplicatas, quantidade removida)
    """
    if df is None or df.empty:
        return df, 0

    qtd_duplicadas = int(df.duplicated().sum())
    if qtd_duplicadas == 0:
        log.info("Deduplicação: nenhum registro 100%% idêntico encontrado.")
        return df, 0

    # Detalhamento por mês (ajuda a identificar qual carga veio repetida)
    if "REFERENCIA" in df.columns:
        detalhe = (
            df.groupby("REFERENCIA", group_keys=False)
            .apply(lambda g: int(g.duplicated().sum()))
        )
        detalhe = detalhe[detalhe > 0]
        resumo_meses = ", ".join(
            f"{ref_to_label(ref)}: {qtd}" for ref, qtd in detalhe.items()
        )
    else:
        resumo_meses = "detalhamento indisponível"

    df_limpo = df.drop_duplicates().reset_index(drop=True)
    log.warning(
        "Deduplicação: %d registro(s) 100%% idêntico(s) removido(s) de %d "
        "(origem: carga duplicada do arquivo consolidado). Detalhe por mês -> %s",
        qtd_duplicadas, len(df), resumo_meses,
    )
    return df_limpo, qtd_duplicadas


def _executar_etl() -> None:
    """Executa o pipeline completo (leitura → enriquecimento → gravação).

    Uso interno: sempre chamado por `run_etl()`, que adiciona tratamento de erro
    e logging de exceção. Levanta `ETLValidationError` em falha estrutural.
    """
    log.info("Iniciando pipeline de ETL e saneamento de dados...")
    main_file = os.path.join(BASE_DIR, "parquesuspenso-janeiro a maio.csv")

    # Leitura com fallback de encoding
    df = df_read_any_csv(main_file)
    if df is None:
        raise ETLValidationError(f"Não foi possível ler a base consolidada: {main_file}")

    # Limpeza de nomes de colunas (remover BOM e espaços)
    df = df_clean_columns(df)

    # Validação de entrada (estrutura + qualidade) antes de transformar
    validar_base(df, origem=os.path.basename(main_file))

    # 0. Ingestão automática de novos arquivos mensais (ex: ParqueSuspenso_junho.csv)
    df, qtd_ingest = ingest_new_months(df)
    if qtd_ingest > 0:
        log.info("Ingestão automática concluída: %d registros anexados de novos meses.", qtd_ingest)
        validar_base(df, origem="consolidado + meses novos")
    else:
        log.info("Nenhum mês novo detectado para ingestão automática.")

    # 0b. Remoção de registros 100% idênticos (carga duplicada do arquivo de origem)
    qtd_deduplicada = 0
    if REMOVER_DUPLICATAS_EXATAS:
        df, qtd_deduplicada = remover_duplicatas_exatas(df)
    else:
        log.info("Deduplicação desativada (REMOVER_DUPLICATAS_EXATAS=False).")

    # 0c. Normalização opcional do aging pela data de suspensão (ver constantes no topo)
    if NORMALIZAR_AGING_POR_REFERENCIA:
        df, qtd_ajustada = normalizar_aging(df)
        log.info("Aging normalizado pela data de suspensão: %d linha(s) ajustada(s).", qtd_ajustada)
    else:
        extracoes = extracoes_por_mes(df)
        inconsistentes = extracoes[~extracoes["CONSISTENTE"]]["REFERENCIA_LABEL"].tolist()
        if inconsistentes:
            log.warning(
                "Aging NÃO normalizado, mas %s têm extração fora do mês de referência. "
                "Ative NORMALIZAR_AGING_POR_REFERENCIA para comparar meses com justiça.",
                ", ".join(inconsistentes),
            )

    # 1. Tratar Telefones e extrair DDD
    df['NUMTELEFONE_STR'] = df['NUMTELEFONE'].astype(str).str.replace(r'\D', '', regex=True)
    df['DDD'] = df['NUMTELEFONE_STR'].str[:2]
    
    # 2. Saneamento de UF ausente usando o DDD
    ufs_iniciais_nulas = df['UF'].isna().sum()
    df['UF_ORIGINAL'] = df['UF']
    
    # Aplicar enriquecimento
    df['UF'] = df['UF'].fillna(df['DDD'].map(DDD_TO_UF))
    # Caso ainda reste nulo, marca como 'Outros'
    df['UF'] = df['UF'].fillna("Outros")
    ufs_finais_nulas = (df['UF'] == "Outros").sum()
    log.info("UFs recuperadas via DDD: %d de %d.", ufs_iniciais_nulas - ufs_finais_nulas, ufs_iniciais_nulas)
    
    # 3. Região Geográfica
    df['REGIAO'] = df['UF'].map(UF_TO_REGION).fillna("Outra")
    
    # 4. Limpeza e ordenação de Aging
    df['AGING_LIMPO'] = df['AGING'].apply(clean_aging)
    aging_order = {
        "Até 30 dias": 1,
        "De 31 a 60 dias": 2,
        "De 61 a 90 dias": 3,
        "De 91 a 120 dias": 4,
        "Maior que 120 dias": 5,
        "Não Informado": 6
    }
    df['AGING_ORDEM'] = df['AGING_LIMPO'].map(aging_order).fillna(99)

    # 5. Classificação de Risco de Churn (Involuntário)
    def classificar_risco(aging: str) -> str:
        """Mapeia a faixa de aging para a faixa de risco de churn involuntário."""
        if aging == "Até 30 dias":
            return "Baixo (Janela de Ouro)"
        elif aging == "De 31 a 60 dias":
            return "Médio (Atenção)"
        elif aging == "De 61 a 90 dias":
            return "Alto (Risco Crítico)"
        else:
            return "Extremo (Pré-Desconexão)"

    df['FAIXA_RISCO'] = df['AGING_LIMPO'].apply(classificar_risco)
    
    # 6. Referência amigável e cronológica (gerada dinamicamente para qualquer mês/ano)
    df['REFERENCIA_LABEL'] = df['REFERENCIA'].apply(ref_to_label)
    
    # 7. Datas
    df['DTPRIMEIRAATIVACAO'] = pd.to_datetime(df['DTPRIMEIRAATIVACAO'], errors='coerce')
    df['DT_SUSPENSAO'] = pd.to_datetime(df['DT_SUSPENSAO'], errors='coerce')
    
    # 8. Formatação do CNPJ
    def formatar_cnpj(v: object) -> str:
        """Formata o CNPJ como 00.000.000/0000-00 (devolve o valor original se inválido)."""
        try:
            s = str(int(float(v))).zfill(14)
            return f"{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:14]}"
        except Exception:
            return str(v)
            
    df['CNPJ_FORMATADO'] = df['CNPJ_CLIENTE'].apply(formatar_cnpj)
    
    # 9. Integração com a coluna MSG de Janeiro (se existir)
    jan_file = os.path.join(BASE_DIR, "ParqueSuspenso_janeiro.csv")
    if os.path.exists(jan_file):
        try:
            df_jan = df_read_any_csv(jan_file)
            df_jan = df_clean_columns(df_jan)
            if 'MSG' in df_jan.columns and 'NUMTELEFONE' in df_jan.columns:
                msg_map = df_jan.drop_duplicates(subset=['NUMTELEFONE']).set_index('NUMTELEFONE')['MSG'].to_dict()
                df['MSG_EXEMPLO'] = df['NUMTELEFONE'].map(msg_map)
                log.info("Mensagens de exemplo integradas a partir de %s (%d correspondências).",
                         os.path.basename(jan_file), int(df['MSG_EXEMPLO'].notna().sum()))
        except Exception as e:
            log.warning("Não foi possível integrar as mensagens de Janeiro: %s", e)

    # Template padrão de cobrança WhatsApp para qualquer linha
    padrao_msg = (
        "Olá! Sou da equipe de suporte corporativo de telecomunicações. "
        "Constatamos uma pendência na(s) linha(s) do seu CNPJ {cnpj} que ocasionou a suspensão. "
        "Para regularização imediata e reativação do sinal com condições especiais, "
        "fale conosco pelo suporte (82) 3024-8079."
    )
    df['MSG_COBRANCA'] = df.apply(
        lambda r: r['MSG_EXEMPLO'] if pd.notna(r.get('MSG_EXEMPLO')) else padrao_msg.format(cnpj=r['CNPJ_FORMATADO']),
        axis=1
    )
    
    # 10. Anonimização: descarte definitivo dos identificadores corporativos
    cols_drop = [c for c in ANONIMIZAR_DROP if c in df.columns]
    if cols_drop:
        df = df.drop(columns=cols_drop)
        log.info("Anonimização: colunas removidas -> %s", cols_drop)

    # 11. Validação final da base tratada (todas as colunas obrigatórias + derivadas)
    validar_base(df, origem="base tratada", obrigatorias=COLUNAS_OBRIGATORIAS + COLUNAS_DERIVADAS)

    # Salvar em Parquet e CSV otimizado
    parquet_path = os.path.join(BASE_DIR, "parque_suspenso_tratado.parquet")
    df.to_parquet(parquet_path, index=False)

    csv_path = os.path.join(BASE_DIR, "parque_suspenso_tratado.csv")
    df.to_csv(csv_path, sep=';', index=False, encoding='utf-8-sig')

    log.info("ETL concluído com sucesso: %d registros | meses: %s | duplicatas removidas: %d",
             len(df), [ref_to_label(r) for r in sorted(df['REFERENCIA'].astype(int).unique())],
             qtd_deduplicada)
    return df


def run_etl() -> None:
    """Executa o ETL completo com tratamento de erros e logging estruturado.

    Raises:
        ETLValidationError: quando a base de entrada é estruturalmente inválida.
        Exception: qualquer falha inesperada, após ser registrada em log.
    """
    try:
        return _executar_etl()
    except ETLValidationError as erro_validacao:
        log.error("ETL interrompido por falha de validação: %s", erro_validacao)
        raise
    except Exception as erro:
        log.exception("Falha inesperada no ETL: %s", erro)
        raise

if __name__ == "__main__":
    run_etl()
