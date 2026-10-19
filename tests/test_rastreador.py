"""Testes do Rastreador Nominal de Recuperação (`rastreador.py`)."""
from __future__ import annotations

import pandas as pd
import pytest


# ------------------------------------------------ persistência

def test_arquivo_ausente_devolve_esquema_vazio(rastreador_tmp):
    acoes = rastreador_tmp.carregar_acoes()
    assert acoes.empty
    assert list(acoes.columns) == rastreador_tmp.COLUNAS


def test_registrar_e_recarregar_acao(rastreador_tmp, base_tratada):
    linha = base_tratada.iloc[0]
    registro = rastreador_tmp.registrar_acao(
        numtelefone=linha["NUMTELEFONE_STR"],
        referencia=int(linha["REFERENCIA"]),
        canal="WhatsApp",
        resultado="Contato efetivo",
        operador="Ana Souza",
        cliente=linha["CLIENTE"],
        observacao="primeiro contato",
    )
    assert registro["ID_ACAO"] == "A00001"

    acoes = rastreador_tmp.carregar_acoes()
    assert len(acoes) == 1
    assert acoes.loc[0, "CANAL"] == "WhatsApp"
    assert acoes.loc[0, "RESULTADO"] == "Contato efetivo"
    assert acoes.loc[0, "OPERADOR"] == "Ana Souza"


def test_ids_sao_sequenciais_e_append_only(rastreador_tmp, base_tratada):
    for i in range(4):
        linha = base_tratada.iloc[i]
        rastreador_tmp.registrar_acao(
            numtelefone=linha["NUMTELEFONE_STR"],
            referencia=int(linha["REFERENCIA"]),
            canal="Ligação",
            resultado="Sem resposta",
            operador="Bruno",
        )
    acoes = rastreador_tmp.carregar_acoes()
    assert list(acoes["ID_ACAO"]) == ["A00001", "A00002", "A00003", "A00004"]


def test_dt_retorno_e_opcional(rastreador_tmp, base_tratada):
    linha = base_tratada.iloc[0]
    rastreador_tmp.registrar_acao(
        numtelefone=linha["NUMTELEFONE_STR"],
        referencia=int(linha["REFERENCIA"]),
        canal="SMS",
        resultado="Promessa de pagamento",
        operador="Ana",
    )
    acoes = rastreador_tmp.carregar_acoes()
    assert pd.isna(acoes.loc[0, "DT_RETORNO"])


def test_observacao_multilinha_vira_linha_unica(rastreador_tmp, base_tratada):
    linha = base_tratada.iloc[0]
    rastreador_tmp.registrar_acao(
        numtelefone=linha["NUMTELEFONE_STR"],
        referencia=int(linha["REFERENCIA"]),
        canal="E-mail",
        resultado="Contato efetivo",
        operador="Ana",
        observacao="linha 1\nlinha 2",
    )
    acoes = rastreador_tmp.carregar_acoes()
    assert "\n" not in acoes.loc[0, "OBSERVACAO"]
    assert len(acoes) == 1


# ------------------------------------------------ validação

@pytest.mark.parametrize(
    "campo_ausente, kwargs_extra",
    [
        ("telefone", {"numtelefone": ""}),
        ("telefone", {"numtelefone": None}),
        ("canal", {"canal": "Carta registrada"}),
        ("resultado", {"resultado": "Talvez"}),
        ("operador", {"operador": "   "}),
        ("referencia", {"referencia": "não-é-mês"}),
    ],
)
def test_registrar_rejeita_campos_invalidos(rastreador_tmp, campo_ausente, kwargs_extra):
    dados = dict(
        numtelefone="81999999999",
        referencia=202605,
        canal="WhatsApp",
        resultado="Recuperado",
        operador="Ana",
    )
    dados.update(kwargs_extra)
    with pytest.raises(rastreador_tmp.AcaoInvalidaError):
        rastreador_tmp.registrar_acao(**dados)

    # Nada deve ter sido gravado
    assert rastreador_tmp.carregar_acoes().empty


# ------------------------------------------------ métricas

def _popular(rt, base, quantidade=6, resultado_padrao=None):
    registros = []
    for i in range(quantidade):
        linha = base.iloc[i]
        registros.append(rt.registrar_acao(
            numtelefone=linha["NUMTELEFONE_STR"],
            referencia=int(linha["REFERENCIA"]),
            canal=rt.CANAIS[i % len(rt.CANAIS)],
            resultado=resultado_padrao or rt.RESULTADOS[i % len(rt.RESULTADOS)],
            operador="Ana" if i % 2 == 0 else "Bruno",
            cliente=linha["CLIENTE"],
            dt_acao=linha["DT_SUSPENSAO"] + pd.Timedelta(days=1 + (i % 3)),
        ))
    return registros


def test_resumo_acoes_vazio(rastreador_tmp, base_tratada):
    kpis = rastreador_tmp.resumo_acoes(rastreador_tmp.carregar_acoes(), base_tratada)
    assert kpis["total_acoes"] == 0
    assert kpis["taxa_conversao"] == 0.0
    assert kpis["tempo_medio_1o_contato"] is None
    assert kpis["pct_dentro_sla"] is None


def test_resumo_acoes_contagens(rastreador_tmp, base_tratada):
    _popular(rastreador_tmp, base_tratada, quantidade=6)
    acoes = rastreador_tmp.carregar_acoes()
    kpis = rastreador_tmp.resumo_acoes(acoes, base_tratada, ticket_medio=45.0)

    assert kpis["total_acoes"] == 6
    assert kpis["linhas_acionadas"] == 6
    assert 0.0 <= kpis["taxa_conversao"] <= 100.0
    assert kpis["tempo_medio_1o_contato"] is not None
    assert kpis["tempo_medio_1o_contato"] >= 0


def test_taxa_conversao_100_por_cento(rastreador_tmp, base_tratada):
    _popular(rastreador_tmp, base_tratada, quantidade=5, resultado_padrao="Recuperado")
    acoes = rastreador_tmp.carregar_acoes()
    kpis = rastreador_tmp.resumo_acoes(acoes, base_tratada, ticket_medio=45.0)
    assert kpis["taxa_conversao"] == 100.0
    assert kpis["linhas_recuperadas"] == 5
    assert kpis["mrr_recuperado"] == pytest.approx(5 * 45.0)


def test_ticket_medio_afeta_mrr(rastreador_tmp, base_tratada):
    _popular(rastreador_tmp, base_tratada, quantidade=4, resultado_padrao="Recuperado")
    acoes = rastreador_tmp.carregar_acoes()
    kpis = rastreador_tmp.resumo_acoes(acoes, base_tratada, ticket_medio=100.0)
    assert kpis["mrr_recuperado"] == pytest.approx(400.0)


def test_sla_por_faixa_reflete_metas(rastreador_tmp, base_tratada):
    _popular(rastreador_tmp, base_tratada, quantidade=6)
    acoes = rastreador_tmp.carregar_acoes()
    tabela = rastreador_tmp.sla_por_faixa(acoes, base_tratada)

    assert not tabela.empty
    assert list(tabela.columns) == [
        "FAIXA_RISCO", "SLA_ALVO_DIAS", "LINHAS_ACIONADAS", "TEMPO_MEDIO", "DENTRO_SLA", "ADERENCIA_%",
    ]
    # Toda faixa presente no domínio deve ter alvo definido
    for alvo in tabela["SLA_ALVO_DIAS"]:
        assert alvo in rastreador_tmp.SLA_RECOMENDADO_DIAS.values()
    assert ((tabela["ADERENCIA_%"] >= 0) & (tabela["ADERENCIA_%"] <= 100)).all()


def test_sla_por_faixa_sem_acoes(rastreador_tmp, base_tratada):
    tabela = rastreador_tmp.sla_por_faixa(rastreador_tmp.carregar_acoes(), base_tratada)
    assert tabela.empty


def test_acoes_por_dimensao(rastreador_tmp, base_tratada):
    _popular(rastreador_tmp, base_tratada, quantidade=6)
    acoes = rastreador_tmp.carregar_acoes()

    por_canal = rastreador_tmp.acoes_por(acoes, "CANAL")
    assert por_canal["ACOES"].sum() == len(acoes)

    por_operador = rastreador_tmp.acoes_por(acoes, "OPERADOR")
    assert set(por_operador["OPERADOR"]) == {"Ana", "Bruno"}


def test_acoes_por_semana(rastreador_tmp, base_tratada):
    _popular(rastreador_tmp, base_tratada, quantidade=6)
    acoes = rastreador_tmp.carregar_acoes()
    semanas = rastreador_tmp.acoes_por_semana(acoes)
    assert not semanas.empty
    assert semanas["ACOES"].sum() == len(acoes)
    assert semanas["SEMANA"].is_monotonic_increasing


def test_recuperacao_observada(base_tratada):
    import rastreador as rt

    tabela = rt.recuperacao_observada(base_tratada)
    if base_tratada["REFERENCIA"].nunique() < 2:
        assert tabela.empty
        return
    assert not tabela.empty
    assert list(tabela.columns) == [
        "REFERENCIA_LABEL", "LINHAS", "SAIRAM", "PERMANECERAM", "TAXA_SAIDA_%",
    ]
    # Linhas que saíram não podem exceder o total do mês
    assert (tabela["SAIRAM"] <= tabela["LINHAS"]).all()
    # Sair + permanecer = total
    assert ((tabela["SAIRAM"] + tabela["PERMANECERAM"]) == tabela["LINHAS"]).all()
    assert ((tabela["TAXA_SAIDA_%"] >= 0) & (tabela["TAXA_SAIDA_%"] <= 100)).all()


def test_responder_enriquece_com_base(rastreador_tmp, base_tratada):
    _popular(rastreador_tmp, base_tratada, quantidade=3)
    acoes = rastreador_tmp.carregar_acoes()
    enriquecido = rastreador_tmp.responder(acoes, base_tratada)
    assert "FAIXA_RISCO" in enriquecido.columns
    assert "DT_SUSPENSAO" in enriquecido.columns
    # Todas as ações foram registradas em linhas existentes na base
    assert enriquecido["FAIXA_RISCO"].notna().all()


def test_responder_com_acoes_vazias(rastreador_tmp, base_tratada):
    enriquecido = rastreador_tmp.responder(rastreador_tmp.carregar_acoes(), base_tratada)
    assert enriquecido.empty
    assert "FAIXA_RISCO" in enriquecido.columns


def test_dominios_de_negocio():
    import rastreador as rt

    assert "WhatsApp" in rt.CANAIS
    assert "Recuperado" in rt.RESULTADOS
    assert rt.RESULTADOS_RECUPERADO == {"Recuperado"}
    for faixa in ["Baixo (Janela de Ouro)", "Médio (Atenção)", "Alto (Risco Crítico)", "Extremo (Pré-Desconexão)"]:
        assert faixa in rt.SLA_RECOMENDADO_DIAS
        assert rt.SLA_RECOMENDADO_DIAS[faixa] >= 1
