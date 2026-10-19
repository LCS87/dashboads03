"""Testes de UI (smoke) do dashboard via `streamlit.testing.v1.AppTest`.

Cobrem: carga inicial, todos os painéis, modo "Todos os Painéis", filtros globais
e o formulário do Rastreador (caminhos de erro e de sucesso).
"""
from __future__ import annotations

import os
import shutil

import pandas as pd
import pytest

from streamlit.testing.v1 import AppTest

app_test = pytest.importorskip("streamlit.testing.v1", reason="AppTest indisponível")

pytestmark = pytest.mark.ui

PAINEIS = [
    "📊 Cockpit Executivo",
    "⏳ Aging & Risco de Churn",
    "🏢 Top Contas & Concentração",
    "🗺️ Inteligência Geográfica",
    "⚡ Régua de Cobrança & Ações",
    "📞 Rastreador de Recuperação",
]

TIMEOUT = 300


@pytest.fixture(scope="module")
def at(projeto_dir):
    """AppTest carregado uma vez por módulo (carga da base é a parte cara)."""
    app = AppTest.from_file(os.path.join(projeto_dir, "app.py"), default_timeout=TIMEOUT)
    app.run()
    return app


@pytest.fixture()
def sem_acoes(projeto_dir):
    """Garante que o rastreador comece sem histórico e restaura o estado ao final."""
    caminho = os.path.join(projeto_dir, "acoes_recuperacao.csv")
    backup = caminho + ".pytest-bak"
    if os.path.exists(caminho):
        shutil.move(caminho, backup)
    try:
        yield caminho
    finally:
        if os.path.exists(caminho):
            os.remove(caminho)
        if os.path.exists(backup):
            shutil.move(backup, caminho)


def test_carga_inicial_sem_excecao(at):
    assert not at.exception


def test_nao_vaza_coluna_anonimizada_na_ui(at):
    """Nenhuma coluna corporativa deve chegar ao dashboard."""
    texto = str(at.session_state)
    for termo in ["NOME_DIRETOR", "NOME_DIVISAO", "CD_DEALER"]:
        assert termo not in texto


@pytest.mark.parametrize("painel", PAINEIS + ["🗂️ Todos os Painéis"])
def test_paineis_renderizam_sem_excecao(at, painel):
    at.pills[0].set_value(painel).run()
    assert not at.exception, f"painel '{painel}' levantou exceção"


def test_filtro_todos_os_meses(at):
    at.pills[0].set_value("📊 Cockpit Executivo").run()
    at.selectbox[-1].set_value("Todos os Meses").run()
    assert not at.exception


def test_filtro_mes_especifico(at):
    at.pills[0].set_value("📊 Cockpit Executivo").run()
    opcoes = at.selectbox[-1].options
    if len(opcoes) > 1:
        at.selectbox[-1].set_value(opcoes[1]).run()
    assert not at.exception


def test_rastreador_sem_acoes_exibe_orientacao(at, sem_acoes):
    at.pills[0].set_value("📞 Rastreador de Recuperação").run()
    assert not at.exception
    assert any("Nenhuma ação registrada" in info.value for info in at.info)


def test_rastreador_formulario_operador_obrigatorio(at, sem_acoes):
    """Sem operador preenchido, o registro deve ser recusado com mensagem amigável."""
    at.pills[0].set_value("📞 Rastreador de Recuperação").run()
    at.button[0].click().run()
    assert not at.exception
    assert any("operador" in erro.value.lower() for erro in at.error)
    assert not os.path.exists(sem_acoes), "nenhuma ação deveria ter sido gravada"


def test_rastreador_registro_bem_sucedido(at, sem_acoes):
    at.pills[0].set_value("📞 Rastreador de Recuperação").run()
    at.text_input(key="rec_operador").set_value("Ana Souza").run()
    at.button[0].click().run()

    assert not at.exception
    assert os.path.exists(sem_acoes), "a ação deveria ter sido persistida"

    gravadas = pd.read_csv(sem_acoes, sep=";", encoding="utf-8-sig")
    assert len(gravadas) == 1
    assert gravadas.loc[0, "OPERADOR"] == "Ana Souza"
    assert gravadas.loc[0, "ID_ACAO"] == "A00001"


def test_rastreador_fluxo_completo_apos_registro(at, sem_acoes):
    """Após registrar, o painel deve passar a exibir KPIs, gráficos e tabelas."""
    at.pills[0].set_value("📞 Rastreador de Recuperação").run()
    at.text_input(key="rec_operador").set_value("Bruno Lima").run()
    at.button[0].click().run()

    at.pills[0].set_value("📊 Cockpit Executivo").run()
    at.pills[0].set_value("📞 Rastreador de Recuperação").run()

    assert not at.exception
    assert len(at.dataframe) >= 2, "esperados: histórico, SLA e/ou recuperação observada"
