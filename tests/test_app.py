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


def _navegacao(app):
    """Devolve o seletor de navegação entre painéis (não o seletor de tema).

    A navegação é identificada pelo rótulo, e não por índice, para que a
    inclusão de novos widgets na sidebar não quebre os testes.
    """
    for p in app.pills:
        if "Navega" in str(getattr(p, "label", "")):
            return p
    raise AssertionError("seletor de navegação entre painéis não encontrado")


def _seletor_tema(app):
    """Devolve o seletor de tema de exibição."""
    for p in app.pills:
        if "Tema" in str(getattr(p, "label", "")):
            return p
    raise AssertionError("seletor de tema não encontrado")


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
    _navegacao(at).set_value(painel).run()
    assert not at.exception, f"painel '{painel}' levantou exceção"


def test_filtro_todos_os_meses(at):
    _navegacao(at).set_value("📊 Cockpit Executivo").run()
    at.selectbox[-1].set_value("Todos os Meses").run()
    assert not at.exception


def test_filtro_mes_especifico(at):
    _navegacao(at).set_value("📊 Cockpit Executivo").run()
    opcoes = at.selectbox[-1].options
    if len(opcoes) > 1:
        at.selectbox[-1].set_value(opcoes[1]).run()
    assert not at.exception


def test_rastreador_sem_acoes_exibe_orientacao(at, sem_acoes):
    _navegacao(at).set_value("📞 Rastreador de Recuperação").run()
    assert not at.exception
    assert any("Nenhuma ação registrada" in info.value for info in at.info)


def test_rastreador_formulario_operador_obrigatorio(at, sem_acoes):
    """Sem operador preenchido, o registro deve ser recusado com mensagem amigável."""
    _navegacao(at).set_value("📞 Rastreador de Recuperação").run()
    at.button[0].click().run()
    assert not at.exception
    assert any("operador" in erro.value.lower() for erro in at.error)
    assert not os.path.exists(sem_acoes), "nenhuma ação deveria ter sido gravada"


def test_rastreador_registro_bem_sucedido(at, sem_acoes):
    _navegacao(at).set_value("📞 Rastreador de Recuperação").run()
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
    _navegacao(at).set_value("📞 Rastreador de Recuperação").run()
    at.text_input(key="rec_operador").set_value("Bruno Lima").run()
    at.button[0].click().run()

    _navegacao(at).set_value("📊 Cockpit Executivo").run()
    _navegacao(at).set_value("📞 Rastreador de Recuperação").run()

    assert not at.exception
    assert len(at.dataframe) >= 2, "esperados: histórico, SLA e/ou recuperação observada"


def test_regua_botao_whatsapp_renderiza_como_botao(at):
    """Regressão do bug: o botão do WhatsApp aparecia como tag HTML em texto puro.

    O cartão de acionamento é emitido em linha única e o botão usa `st.link_button`,
    que não passa pelo parser de Markdown.
    """
    _navegacao(at).set_value("⚡ Régua de Cobrança & Ações").run()
    assert not at.exception

    # deve existir um link_button (não um <a href> solto no markdown)
    assert len(at.button) >= 0
    links = [b for b in at.get("link_button") or []]
    assert links, "esperado um link_button 'Abrir Conversa no WhatsApp'"

    rotulos = " ".join(str(getattr(b, "label", "")) for b in links)
    assert "WhatsApp" in rotulos

    # nenhum markdown deve conter a tag <a href vazada como texto
    for md in at.markdown:
        assert "<a href=" not in md.value, "tag <a href> vazou como texto no markdown"


def test_tema_claro_e_aplicado_sem_excecao(at):
    """A troca de tema deve rodar limpa e refletir as cores do tema claro."""
    seletor = _seletor_tema(at)
    assert seletor.value == "escuro", f"tema inicial: {seletor.value!r}"

    seletor.set_value("claro").run()
    assert not at.exception
    assert seletor.value == "claro"
    assert at.session_state["tema_nome"] == "claro"

    # o CSS aplicado deve conter as cores do tema claro
    css = " ".join(md.value for md in at.markdown)
    assert "#F2F2F0" in css, "fundo do tema claro ausente no CSS"
    assert "#1A1A1C" in css, "texto do tema claro ausente no CSS"

    # volta para o tema escuro
    _seletor_tema(at).set_value("escuro").run()
    assert not at.exception
    assert at.session_state["tema_nome"] == "escuro"


def test_graficos_do_geografico_renderizam(at):
    """A aba Geográfica usa rampa sequencial do tema (não as escalas azuis do Plotly)."""
    _navegacao(at).set_value("🗺️ Inteligência Geográfica").run()
    assert not at.exception
    assert len(at.get("plotly_chart")) >= 2
