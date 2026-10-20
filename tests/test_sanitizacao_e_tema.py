"""Testes das correções de Sanitização, Tema e Renderização.

Cobre três frentes introduzidas na rodada de saneamento:

1. **Sanitização** — a base tratada não pode conter o nome da empresa, nome de
   gerente/diretor nem telefone real de atendimento.
2. **Tema** — a paleta Gótica Vitoriana está centralizada em `tema.py` e é
   consistente entre CSS, gráficos Plotly e relatório em PDF.
3. **Renderização** — o cartão de acionamento do WhatsApp não pode voltar a
   aparecer como texto literal (bug de Markdown: indentação ≥ 4 espaços vira
   bloco de código e linha em branco encerra o bloco HTML).
"""
from __future__ import annotations

import re

import pytest

import etl_pipeline as etl
import tema


# =========================================================
# 1. SANITIZAÇÃO DE MENSAGENS
# =========================================================

class TestSanitizarMensagem:
    """A mensagem exibida jamais pode identificar a empresa ou uma pessoa."""

    def test_substitui_nome_da_empresa(self):
        msg = etl.sanitizar_mensagem("Olá, sou do setor de qualidade da VIVO Empresas.")
        assert "VIVO" not in msg.upper()
        assert etl.NOME_EMPRESA_GENERICO in msg

    def test_substitui_nome_da_empresa_variante_caixa(self):
        msg = etl.sanitizar_mensagem("Fale com a vivo empresas no app.")
        assert "vivo" not in msg.lower()
        assert etl.NOME_EMPRESA_GENERICO in msg

    def test_substitui_telefone_real_de_atendimento(self):
        msg = etl.sanitizar_mensagem("Entre em contato com 8230248079 e fale com o suporte.")
        assert "8230248079" not in msg
        assert etl.TELEFONE_GENERICO in msg

    def test_substitui_telefone_com_mascara(self):
        msg = etl.sanitizar_mensagem("Ligue para (82) 3024-8079.")
        assert "3024-8079" not in msg
        assert etl.TELEFONE_GENERICO in msg

    def test_substitui_nome_de_diretor_e_gerente(self):
        msg = etl.sanitizar_mensagem(
            "Fale com CLAUDIO RIBEIRO DE JESUS ou LUIS OTAVIO CAVALCANTI MONTIBELO."
        )
        assert "CLAUDIO RIBEIRO" not in msg.upper()
        assert "LUIS OTAVIO" not in msg.upper()
        assert "GERENTE" not in msg.upper()

    def test_mensagem_vazia_e_nula(self):
        assert etl.sanitizar_mensagem("") == ""
        assert etl.sanitizar_mensagem(None) == ""
        assert etl.sanitizar_mensagem(float("nan")) == ""

    def test_nao_altera_mensagem_ja_limpa(self):
        msg = "Prezado cliente, sua fatura está em aberto. Fale com o suporte."
        assert etl.sanitizar_mensagem(msg) == msg

    def test_concordancia_do_nome_generico(self):
        msg = etl.sanitizar_mensagem("Baixe pelo aplicativo do VIVO Empresas.")
        assert "do Telecomunicação" not in msg
        assert "da Telecomunicação" in msg

    def test_nao_repete_nome_generico_na_mesma_frase(self):
        msg = etl.sanitizar_mensagem("VIVO Empresas, aqui é da VIVO Empresas.")
        assert msg.count(etl.NOME_EMPRESA_GENERICO) == 1

    def test_remove_espacos_duplicados(self):
        msg = etl.sanitizar_mensagem("Olá   mundo  do  suporte.")
        assert "  " not in msg


class TestBaseTratadaNaoIdentificaEmpresa:
    """A base tratada gravada em disco não pode conter o nome da empresa."""

    def test_base_tratada_sem_nome_da_empresa(self, base_tratada):
        if "MSG_COBRANCA" not in base_tratada.columns:
            pytest.skip("base sem coluna MSG_COBRANCA")
        mensagens = base_tratada["MSG_COBRANCA"].fillna("").astype(str)
        for nome in etl.NOMES_EMPRESA_PROIBIDOS:
            assert not mensagens.str.contains(re.escape(nome), case=False).any(), (
                f"a base tratada ainda cita {nome!r}"
            )

    def test_base_tratada_sem_telefone_real(self, base_tratada):
        if "MSG_COBRANCA" not in base_tratada.columns:
            pytest.skip("base sem coluna MSG_COBRANCA")
        mensagens = base_tratada["MSG_COBRANCA"].fillna("").astype(str)
        for tel in etl.TELEFONES_PROIBIDOS:
            if tel.strip():
                assert not mensagens.str.contains(re.escape(tel), case=False).any()


# =========================================================
# 2. TEMA GÓTICO VITORIANO
# =========================================================

class TestTema:
    """A paleta deve estar centralizada e ser consistente entre os artefatos."""

    def test_paleta_com_valores_definidos(self):
        assert tema.GRAFITE == "#111111"
        assert tema.CHUMBO == "#1C1C1E"
        assert tema.LARANJA_FERRUGEM == "#CC5500"
        assert tema.CIANO_ENFERRUJADO == "#008B8B"
        assert tema.BRANCO_SUJO == "#D4D4D4"
        assert tema.VERMELHO_OXIDO == "#B22222"
        assert tema.VERDE_PETROLEO == "#006D5B"

    def test_todas_as_cores_sao_hex_validos(self):
        cores = [
            tema.GRAFITE, tema.CHUMBO, tema.LARANJA_FERRUGEM,
            tema.CIANO_ENFERRUJADO, tema.BRANCO_SUJO, tema.VERMELHO_OXIDO,
            tema.VERDE_PETROLEO,
        ]
        for cor in cores:
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", cor), cor

    def test_existe_tema_escuro_e_claro(self):
        assert set(tema.TEMAS) == {"escuro", "claro"}
        assert tema.obter_tema("escuro") is tema.TEMA_ESCURO
        assert tema.obter_tema("claro") is tema.TEMA_CLARO
        assert tema.obter_tema("inexistente") is tema.TEMA_PADRAO

    def test_rampa_de_aging_tem_cinco_tons_distintos(self):
        for t in tema.TEMAS.values():
            assert len(t.aging) == 5
            assert len(set(t.aging.values())) == 5, (
                f"as faixas de aging do tema {t.nome} precisam de tons distintos"
            )

    def test_rampa_de_aging_cobre_todas_as_faixas(self):
        for t in tema.TEMAS.values():
            for faixa in ["Até 30 dias", "De 31 a 60 dias", "De 61 a 90 dias",
                          "De 91 a 120 dias", "Maior que 120 dias"]:
                assert faixa in t.aging

    def test_cores_de_faixa_cobrem_os_niveis(self):
        for t in tema.TEMAS.values():
            assert set(t.faixas) == {
                "Baixo (Janela de Ouro)", "Médio (Atenção)",
                "Alto (Risco Crítico)", "Extremo (Pré-Desconexão)",
            }
            assert len(set(t.faixas.values())) == 4

    def test_rampa_sequencial_e_monotonica(self):
        for t in tema.TEMAS.values():
            lums = [tema._luminancia(c) for c in t.rampa]
            crescente = all(lums[i] < lums[i + 1] for i in range(len(lums) - 1))
            decrescente = all(lums[i] > lums[i + 1] for i in range(len(lums) - 1))
            assert crescente or decrescente, f"rampa do tema {t.nome} nao e monotonica"

    def test_template_plotly_usa_a_paleta(self):
        for t in tema.TEMAS.values():
            layout = tema.template_plotly(t).layout
            assert layout.font.color == t.texto
            assert layout.title.font.color == t.acento
            assert list(layout.colorway) == list(t.colorway)

    def test_aplicar_tema_registra_o_template(self):
        import plotly.graph_objects as go
        for t in tema.TEMAS.values():
            fig = tema.aplicar_tema(go.Figure(), t)
            assert fig.layout.template.layout.font.color == t.texto

    def test_css_tema_contem_as_cores_do_tema(self):
        for t in tema.TEMAS.values():
            css = tema.css_tema(t)
            assert t.fundo in css
            assert t.card in css
            assert t.texto in css
            assert t.acento in css
            assert t.alerta in css
            assert t.positivo in css

    def test_config_toml_do_streamlit_usa_a_paleta(self, projeto_dir):
        """O config.toml é o tema base do Streamlit (lido na partida).

        Ele carrega a **paleta da marca**; as variantes com contraste mais alto
        são aplicadas em tempo de execução pelo CSS do tema.
        """
        import os
        caminho = os.path.join(projeto_dir, ".streamlit", "config.toml")
        if not os.path.exists(caminho):
            pytest.skip("config.toml ausente")
        with open(caminho, encoding="utf-8") as fh:
            conteudo = fh.read()
        for cor in (tema.GRAFITE, tema.CHUMBO, tema.BRANCO_SUJO, tema.LARANJA_FERRUGEM):
            assert cor in conteudo, f"{cor} ausente do config.toml"


class TestAcessibilidade:
    """Contrastes WCAG 2.1 de todos os pares de cor efetivamente usados.

    Regressão do problema encontrado na paleta original: o vermelho sangue e o
    verde musgo, usados como cor de *texto* sobre fundo escuro, ficavam em
    1,92:1 e 1,96:1 — praticamente ilegíveis.
    """

    # (descricao, cor, fundo, razao minima)
    PARES_TEXTO = [
        ("texto principal sobre fundo", "texto", "fundo", 4.5),
        ("texto principal sobre card", "texto", "card", 4.5),
        ("texto secundario sobre fundo", "texto_sec", "fundo", 4.5),
        ("texto secundario sobre card", "texto_sec", "card", 4.5),
        ("acento sobre fundo", "acento", "fundo", 4.5),
        ("acento sobre card", "acento", "card", 4.5),
        ("alerta sobre fundo", "alerta", "fundo", 4.5),
        ("alerta sobre card", "alerta", "card", 4.5),
        ("positivo sobre fundo", "positivo", "fundo", 4.5),
        ("positivo sobre card", "positivo", "card", 4.5),
        ("perigo sobre fundo", "perigo", "fundo", 4.5),
        ("perigo sobre card", "perigo", "card", 4.5),
    ]

    @pytest.mark.parametrize("nome_tema", ["escuro", "claro"])
    def test_contraste_de_texto_atende_aa(self, nome_tema):
        t = tema.obter_tema(nome_tema)
        for desc, attr_fg, attr_bg, minimo in self.PARES_TEXTO:
            fg = getattr(t, attr_fg)
            bg = getattr(t, attr_bg)
            razao = tema.contraste(fg, bg)
            assert razao >= minimo, (
                f"[{nome_tema}] {desc}: {fg} sobre {bg} = {razao:.2f}:1 "
                f"(minimo {minimo}:1)"
            )

    @pytest.mark.parametrize("nome_tema", ["escuro", "claro"])
    def test_contraste_nao_textual_atende_aa(self, nome_tema):
        """Barras, bordas e faixas: >= 3:1 (WCAG 1.4.11)."""
        t = tema.obter_tema(nome_tema)
        for faixa, cor in t.faixas.items():
            razao = tema.contraste(cor, t.card)
            assert razao >= 3.0, f"[{nome_tema}] faixa '{faixa}': {razao:.2f}:1"
        for faixa, cor in t.aging.items():
            razao = tema.contraste(cor, t.card)
            assert razao >= 3.0, f"[{nome_tema}] aging '{faixa}': {razao:.2f}:1"
        razao = tema.contraste(t.rampa[-1], t.card)
        assert razao >= 3.0, f"[{nome_tema}] topo da rampa: {razao:.2f}:1"

    @pytest.mark.parametrize("nome_tema", ["escuro", "claro"])
    def test_botao_primario_tem_contraste(self, nome_tema):
        t = tema.obter_tema(nome_tema)
        razao = tema.contraste(t.cor_texto_sobre_primario, t.primario)
        assert razao >= 4.5, f"[{nome_tema}] botao primario: {razao:.2f}:1"

    @pytest.mark.parametrize("nome_tema", ["escuro", "claro"])
    def test_paleta_da_marca_nao_e_usada_como_texto_sem_ajuste(self, nome_tema):
        """As cores puras da marca nao podem ser usadas como texto no tema escuro.

        Laranja ferrugem, oxido e verde petroleo sao escuros demais sobre fundo
        escuro; o tema deve usar as variantes clareadas.
        """
        t = tema.obter_tema(nome_tema)
        if nome_tema == "escuro":
            assert t.alerta != tema.VERMELHO_OXIDO, "oxido puro nao serve como texto no escuro"
            assert t.positivo != tema.VERDE_PETROLEO, "petroleo puro nao serve como texto no escuro"
            assert t.acento != tema.LARANJA_FERRUGEM, "ferrugem pura nao serve como texto no escuro"

    @pytest.mark.parametrize("nome_tema", ["escuro", "claro"])
    def test_botao_primario_tem_contraste_com_texto_branco(self, nome_tema):
        """O botao primario precisa de 4,5:1 com o texto branco que recebe."""
        t = tema.obter_tema(nome_tema)
        razao = tema.contraste(t.cor_texto_sobre_primario, t.primario)
        assert razao >= 4.5, f"[{nome_tema}] botao primario: {razao:.2f}:1"

    def test_paleta_do_pdf_contrasta_com_papel(self):
        """O relatorio e impresso: os textos precisam contraste sobre papel."""
        t = tema.TEMA_ESCURO
        for attr in ("pdf_texto", "pdf_texto_sec", "pdf_acento", "pdf_alerta",
                     "pdf_positivo", "pdf_perigo"):
            razao = tema.contraste(getattr(t, attr), t.pdf_fundo)
            assert razao >= 4.5, f"PDF {attr}: {razao:.2f}:1"

    def test_contraste_calculado_corretamente(self):
        """Sanidade do calculo WCAG: preto x branco = 21:1."""
        assert abs(tema.contraste("#000000", "#FFFFFF") - 21.0) < 0.01
        assert abs(tema.contraste("#FFFFFF", "#FFFFFF") - 1.0) < 0.01


# =========================================================
# 3. RENDERIZAÇÃO (regressão do bug do WhatsApp)
# =========================================================

class TestRenderizacaoWhatsapp:
    """O cartão de acionamento não pode degradar para texto literal.

    Regressão do bug: o HTML era emitido com indentação ≥ 4 espaços e com
    linhas em branco, o que fazia o parser Markdown transformá-lo em bloco
    de código — o usuário via a tag ``<a href=...>`` impressa na tela.
    """

    @pytest.fixture(scope="class")
    def markdown_it(self):
        md = pytest.importorskip("markdown_it")
        return md.MarkdownIt("commonmark")

    def test_html_sem_indentacao_nao_vira_bloco_de_codigo(self, markdown_it):
        html = markdown_it.render("<div style='color: red'>conteudo</div>")
        assert "<pre>" not in html
        assert "<code>" not in html
        assert "<div" in html

    def test_html_indentado_vira_bloco_de_codigo(self, markdown_it):
        """Documenta a armadilha: 4+ espaços de indentação = bloco de código."""
        html = markdown_it.render("\n    <div>conteudo</div>\n")
        assert "<pre>" in html, "a indentação deveria criar bloco de código"

    def test_linha_em_branco_encerra_o_bloco_html(self, markdown_it):
        """Documenta a armadilha: linha em branco encerra o bloco HTML.

        Depois do branco, o conteúdo sai do bloco HTML e passa a ser Markdown
        comum — e, se estiver indentado ≥ 4 espaços, vira bloco de código.
        """
        html = markdown_it.render("<div>\n\n    <a href='#'>botao</a>\n</div>\n")
        assert "<pre>" in html, "o trecho indentado após a linha em branco virou código"
        assert "&lt;a href" in html, "a tag deveria ter aparecido como texto literal"

    def test_linha_em_branco_sem_indentacao_mantem_html_valido(self, markdown_it):
        """Sem indentação, o conteúdo após a linha em branco ainda vira HTML."""
        html = markdown_it.render("<div>\n\n<a href='#'>botao</a>\n</div>\n")
        assert "<a href" in html
        assert "<pre>" not in html

    def test_cartao_do_app_e_emitido_em_linha_unica(self, projeto_dir):
        """O cartão gerado pelo app não pode conter indentação nem linha em branco."""
        import os
        caminho = os.path.join(projeto_dir, "app.py")
        with open(caminho, encoding="utf-8") as fh:
            fonte = fh.read()
        # localiza a construção do cartão de acionamento
        inicio = fonte.index("cartao = (")
        fim = fonte.index("st.markdown(cartao, unsafe_allow_html=True)", inicio)
        bloco = fonte[inicio:fim]
        # o texto do código-fonte é indentado, mas as *strings* não podem ter
        # quebra de linha nem espaço no início (que o Markdown trataria como código)
        literais = re.findall(r"'([^']*)'", bloco)
        for literal in literais:
            if "<" in literal:
                assert "\n" not in literal, "literal de HTML não pode conter quebra de linha"
                assert not literal.startswith(" "), "literal de HTML não pode começar com espaço"

    def test_app_nao_emite_ancora_html_com_texto_multilinha(self, projeto_dir):
        """Não pode existir '<a href=...' quebrado em várias linhas (bug original)."""
        import os
        caminho = os.path.join(projeto_dir, "app.py")
        with open(caminho, encoding="utf-8") as fh:
            fonte = fh.read()
        # a tag <a href deve estar sempre na mesma linha do fechamento </a>
        for match in re.finditer(r"<a href=.*?</a>", fonte, re.S):
            trecho = match.group(0)
            assert "\n" not in trecho, "âncora HTML não pode ter quebra de linha"
