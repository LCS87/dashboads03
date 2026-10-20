"""Sistema de temas do dashboard — Gótico Vitoriano (escuro) e Pergaminho (claro).

Fonte única de verdade das cores, dos estilos CSS e dos templates Plotly.

Objetivo
--------
Manter uma **identidade visual vitoriana** (sangue, ouro, pergaminho, bordô) em
dois modos de exibição, com **contraste WCAG 2.1 AA verificado** em todos os pares
de cor efetivamente usados:

- **Escuro** — Gótico Vitoriano: preto carvão, bordô escuro, vermelho sangue,
  dourado envelhecido, pergaminho, cinza ferrugem, carmesim, verde musgo.
- **Claro** — Pergaminho: papel envelhecido, tinta sepia, sangue e ouro escuros.

Regras de acessibilidade aplicadas
----------------------------------
1. A paleta **da marca** (as 8 cores do briefing) é preservada como cor de
   *preenchimento*, borda e acento gráfico.
2. Como texto sobre fundo escuro, as cores saturadas escuras (sangue, musgo,
   carmesim) são substituídas por **variantes de luminosidade do mesmo matiz**
   (H e S preservados), que atingem ≥ 4,5:1.
3. O mesmo vale no sentido inverso no tema claro: o dourado é escurecido para
   continuar legível sobre papel.
4. Barras, bordas e demais elementos não textuais atingem ≥ 3:1 (WCAG 1.4.11).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import plotly.graph_objects as go

# =====================================================================
# PALETA DA MARCA (briefing) — usada como preenchimento / acento gráfico
# =====================================================================

PRETO_CARVAO = "#0D0D0D"          # background principal
BORDO_ESCURO = "#1A0A0A"          # cards e sidebar
VERMELHO_SANGUE = "#8B0000"       # acento primário
DOURADO_ENVELHECIDO = "#B8860B"   # acento secundário
PERGAMINHO = "#E8DCC8"            # texto principal
CINZA_FERRUGEM = "#8B7D6B"        # texto secundário
CARMESIM = "#DC143C"              # alerta / risco
VERDE_MUSGO = "#2E4A2E"           # sucesso / positivo

#: Nome da empresa exibido na interface (nunca a razão social real).
NOME_EMPRESA = "Telecomunicação S/A"

#: Telefone de suporte exibido nas mensagens de cobrança (genérico).
TELEFONE_SUPORTE = "(00) 00000-0000"


# =====================================================================
# MODELO DE TEMA
# =====================================================================

@dataclass(frozen=True)
class Tema:
    """Conjunto completo de cores de um tema de exibição."""

    nome: str
    rotulo: str
    emoji: str

    fundo: str                 # fundo da aplicação
    card: str                  # fundo dos cartões
    card_alto: str             # campos de entrada / elementos elevados
    borda: str                 # borda sutil
    borda_forte: str           # borda de destaque

    texto: str                 # texto principal
    texto_sec: str             # texto secundário / rótulos

    acento: str                # acento secundário (dourado) já com contraste válido
    acento_claro: str          # variante clara do acento (bordas finas)
    primario: str              # acento primário (fundo de botão)

    alerta: str                # carmesim — falha crítica
    positivo: str              # verde musgo — sucesso
    perigo: str                # vermelho sangue — risco iminente

    faixas: dict = field(default_factory=dict)   # faixas de risco
    aging: dict = field(default_factory=dict)     # faixas de aging
    rampa: tuple = ()                            # escala sequencial
    colorway: tuple = ()                         # cores distintas de séries
    grade: str = ""                              # cor das linhas de grade

    # --- paleta do relatório em PDF (fundo de papel, sempre impresso) ---
    pdf_fundo: str = "#FFFFFF"
    pdf_cartao: str = "#FFFFFF"
    pdf_cabecalho: str = "#2A0A0A"
    pdf_texto: str = "#1A1008"
    pdf_texto_sec: str = "#6B5B4A"
    pdf_borda: str = "#D5CCBB"
    pdf_trilho: str = "#D5CCBB"
    pdf_acento: str = "#876207"
    pdf_alerta: str = "#C21038"
    pdf_positivo: str = "#2E4A2E"
    pdf_perigo: str = "#8B0000"

    # -----------------------------------------------------------------
    # Propriedades derivadas
    # -----------------------------------------------------------------

    @property
    def cor_texto_sobre_primario(self) -> str:
        """Cor de texto sobre o fundo do botão primário."""
        return "#FFFFFF"

    def cor_sobre(self, fundo: str) -> str:
        """Escolhe entre texto claro e escuro conforme o fundo informado."""
        return self.texto if _luminancia(fundo) < 0.45 else "#1A1008"


# ---------------------------------------------------------------------
# Utilidades de contraste (usadas nos testes de acessibilidade)
# ---------------------------------------------------------------------

def _canal(v: float) -> float:
    v = v / 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def _luminancia(hex_cor: str) -> float:
    """Luminância relativa (WCAG 2.1) de uma cor hexadecimal."""
    h = hex_cor.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _canal(r) + 0.7152 * _canal(g) + 0.0722 * _canal(b)


def contraste(cor1: str, cor2: str) -> float:
    """Razão de contraste WCAG entre duas cores (1.0 a 21.0)."""
    l1, l2 = _luminancia(cor1), _luminancia(cor2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def nivel_contraste(razao: float) -> str:
    """Classifica uma razão de contraste segundo a WCAG 2.1."""
    if razao >= 7.0:
        return "AAA"
    if razao >= 4.5:
        return "AA"
    if razao >= 3.0:
        return "AA-large"
    return "FALHA"


# =====================================================================
# TEMA ESCURO — Gótico Vitoriano
# =====================================================================

TEMA_ESCURO = Tema(
    nome="escuro",
    rotulo="Gótico Vitoriano (escuro)",
    emoji="🌙",
    fundo=PRETO_CARVAO,
    card=BORDO_ESCURO,
    card_alto="#241212",
    borda="rgba(232, 220, 200, 0.10)",
    borda_forte="rgba(184, 134, 11, 0.45)",
    texto=PERGAMINHO,
    texto_sec=CINZA_FERRUGEM,
    acento=DOURADO_ENVELHECIDO,      # 5,91:1 sobre card
    acento_claro="#D4AF37",
    primario=VERMELHO_SANGUE,
    alerta="#EB264E",                # carmesim clareado — 4,51:1
    positivo="#548654",              # musgo clareado — 4,50:1
    perigo="#CC5555",                # sangue clareado — 4,58:1
    faixas={
        "Baixo (Janela de Ouro)": "#548654",
        "Médio (Atenção)": "#B8860B",
        "Alto (Risco Crítico)": "#EB264E",
        "Extremo (Pré-Desconexão)": "#CC5555",
    },
    aging={
        "Até 30 dias": "#548654",
        "De 31 a 60 dias": "#7A6A1E",
        "De 61 a 90 dias": "#B8860B",
        "De 91 a 120 dias": "#C1440E",
        "Maior que 120 dias": "#CC5555",
    },
    rampa=("#45211F", "#6E1A1A", "#8B0000", "#B31212", "#D4AF37"),
    colorway=("#B8860B", "#EB264E", "#548654", "#CC5555",
               "#E8DCC8", "#8B7D6B", "#D4AF37", "#5C0011"),
    grade="rgba(232, 220, 200, 0.10)",
)

# =====================================================================
# TEMA CLARO — Pergaminho
# =====================================================================

TEMA_CLARO = Tema(
    nome="claro",
    rotulo="Pergaminho (claro)",
    emoji="☀️",
    fundo="#F3EBDC",
    card="#FCF8EF",
    card_alto="#FFFFFF",
    borda="rgba(42, 30, 20, 0.16)",
    borda_forte="rgba(139, 0, 0, 0.38)",
    texto="#2A1E14",                # tinta sepia — 13,7:1
    texto_sec="#6B5B4A",            # 5,50:1
    acento="#876207",               # ouro escuro — 4,69:1
    acento_claro="#B8860B",
    primario=VERMELHO_SANGUE,
    alerta="#C21038",               # carmesim escuro — 5,18:1
    positivo="#2E4A2E",             # musgo — 8,30:1
    perigo="#8B0000",               # sangue — 8,45:1
    faixas={
        "Baixo (Janela de Ouro)": "#3F6B3F",
        "Médio (Atenção)": "#876207",
        "Alto (Risco Crítico)": "#C21038",
        "Extremo (Pré-Desconexão)": "#8B0000",
    },
    aging={
        "Até 30 dias": "#3F6B3F",
        "De 31 a 60 dias": "#7A6A1E",
        "De 61 a 90 dias": "#876207",
        "De 91 a 120 dias": "#A63A0A",
        "Maior que 120 dias": "#8B0000",
    },
    rampa=("#E5D8B6", "#DCC178", "#B8860B", "#8B0000", "#5C0011"),
    colorway=("#8B0000", "#876207", "#C21038", "#3F6B3F",
               "#2A1E14", "#6B5B4A", "#B8860B", "#5C0011"),
    grade="rgba(42, 30, 20, 0.14)",
)

TEMAS = {TEMA_ESCURO.nome: TEMA_ESCURO, TEMA_CLARO.nome: TEMA_CLARO}
TEMA_PADRAO = TEMA_ESCURO


def obter_tema(nome: str | None) -> Tema:
    """Devolve o tema pelo nome, com fallback para o tema padrão."""
    return TEMAS.get(str(nome).lower(), TEMA_PADRAO)


# =====================================================================
# TEMPLATE PLOTLY
# =====================================================================

def template_plotly(tema: Tema) -> go.layout.Template:
    """Template Plotly do tema, com eixos, legenda e rótulos nas cores do tema."""
    eixo = {
        "gridcolor": tema.grade,
        "linecolor": tema.grade,
        "zerolinecolor": tema.grade,
        "tickfont": {"color": tema.texto_sec, "size": 11},
        "title": {"font": {"color": tema.texto, "size": 12}},
        "automargin": True,
    }
    return go.layout.Template(
        layout={
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {
                "family": "'Plus Jakarta Sans', 'Segoe UI', sans-serif",
                "color": tema.texto,
                "size": 12,
            },
            "colorway": list(tema.colorway),
            "title": {
                "font": {
                    "color": tema.acento,
                    "size": 15,
                    "family": "'Plus Jakarta Sans', sans-serif",
                },
                "x": 0.0,
                "xanchor": "left",
            },
            "xaxis": dict(eixo),
            "yaxis": dict(eixo),
            "legend": {
                "font": {"color": tema.texto, "size": 11},
                "bgcolor": "rgba(0,0,0,0)",
                "bordercolor": tema.grade,
            },
            "hoverlabel": {
                "bgcolor": tema.card,
                "bordercolor": tema.acento,
                "font": {"color": tema.texto, "size": 12},
            },
            "margin": {"l": 10, "r": 10, "t": 40, "b": 10},
        }
    )


def aplicar_tema(fig: go.Figure, tema: Tema) -> go.Figure:
    """Aplica o tema do dashboard a uma figura Plotly.

    As cores são definidas **explicitamente** no layout (e não apenas via
    ``template``). Motivo: o Plotly faz *merge* do template com o template
    padrão e, em alguns componentes, o padrão prevalece — o que fazia os
    rótulos dos eixos ficarem na cor clara do tema padrão do Plotly
    (``#E6EAF1``), invisíveis sobre o fundo de papel do tema claro.

    Propriedades explícitas do layout sempre têm prioridade sobre o template.
    """
    grade = tema.grade
    fig.update_layout(
        template=template_plotly(tema),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="'Plus Jakarta Sans', 'Segoe UI', sans-serif",
            color=tema.texto,
            size=12,
        ),
        colorway=list(tema.colorway),
        title=dict(font=dict(color=tema.acento, size=15, family="'Plus Jakarta Sans', sans-serif")),
        xaxis=dict(
            tickfont=dict(color=tema.texto_sec, size=11),
            title=dict(font=dict(color=tema.texto, size=12)),
            gridcolor=grade,
            linecolor=grade,
            zerolinecolor=grade,
            automargin=True,
        ),
        yaxis=dict(
            tickfont=dict(color=tema.texto_sec, size=11),
            title=dict(font=dict(color=tema.texto, size=12)),
            gridcolor=grade,
            linecolor=grade,
            zerolinecolor=grade,
            automargin=True,
        ),
        legend=dict(
            font=dict(color=tema.texto, size=11),
            title=dict(font=dict(color=tema.texto, size=12)),
            bgcolor="rgba(0,0,0,0)",
            bordercolor=grade,
        ),
        hoverlabel=dict(
            bgcolor=tema.card,
            bordercolor=tema.acento,
            font=dict(color=tema.texto, size=12),
        ),
    )
    return fig


# =====================================================================
# CSS DINÂMICO
# =====================================================================

def css_tema(tema: Tema) -> str:
    """Gera o CSS completo do tema (aplicado via `st.markdown`).

    Inclui o reset do tema base do Streamlit para que a troca de tema
    funcione em tempo de execução, sem reiniciar o servidor.
    """
    return f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', sans-serif; }}

    /* Títulos em serifa vitoriana */
    .header-title, h1, h2, h3, h4, h5, h6,
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {{
        font-family: 'Playfair Display', Georgia, serif !important;
        letter-spacing: 0.2px;
    }}

    /* ---------- Reset do tema base do Streamlit ---------- */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
    [data-testid="stToolbar"], .main, [data-testid="stMainBlockContainer"] {{
        background-color: {tema.fundo} !important;
        color: {tema.texto} !important;
    }}
    [data-testid="stSidebar"], [data-testid="stSidebar"] > div,
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        background-color: {tema.card} !important;
        color: {tema.texto} !important;
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{
        color: {tema.texto} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
        color: {tema.texto_sec} !important;
    }}
    .stButton > button, .stDownloadButton > button {{
        background-color: {tema.card_alto} !important;
        color: {tema.texto} !important;
        border: 1px solid {tema.borda} !important;
    }}
    [data-testid="stBaseButton-primary"] {{
        background-color: {tema.primario} !important;
        color: {tema.cor_texto_sobre_primario} !important;
        border: 1px solid {tema.primario} !important;
    }}
    [data-baseweb="input"] > div, [data-baseweb="base-select"] > div,
    [data-baseweb="input"] input, textarea {{
        background-color: {tema.card_alto} !important;
        color: {tema.texto} !important;
        border-color: {tema.borda} !important;
    }}
    [data-testid="stExpander"] {{
        background-color: {tema.card} !important;
        border-color: {tema.borda} !important;
    }}
    [data-testid="stDataFrame"], [data-testid="stDataFrame"] * {{
        background-color: {tema.card} !important;
    }}
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {{
        color: {tema.texto} !important;
    }}
    [data-testid="stAlert"] {{ background-color: {tema.card} !important; }}

    /* ---------- Cabeçalho ---------- */
    .header-box {{
        background: linear-gradient(135deg, {tema.card_alto} 0%, {tema.fundo} 100%);
        border: 1px solid {tema.borda};
        border-top: 2px solid {tema.borda_forte};
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.35);
        backdrop-filter: blur(12px);
    }}
    .header-title {{
        font-size: 26px;
        font-weight: 800;
        letter-spacing: -0.5px;
        background: linear-gradient(90deg, {tema.acento_claro}, {tema.alerta}, {tema.primario});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }}
    .header-sub {{ color: {tema.texto_sec}; font-size: 13.5px; margin-top: 6px; display: flex; gap: 20px; flex-wrap: wrap; }}
    .header-badge {{
        background: {tema.borda};
        color: {tema.acento};
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid {tema.borda_forte};
    }}

    /* ---------- Cartões de KPI ---------- */
    .metric-card {{
        background: linear-gradient(145deg, {tema.card_alto} 0%, {tema.card} 100%);
        border: 1px solid {tema.borda};
        border-top: 2px solid {tema.borda_forte};
        border-radius: 14px;
        padding: 20px;
        transition: transform 0.2s ease, border-color 0.2s ease;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.22);
    }}
    .metric-card:hover {{ transform: translateY(-2px); border-color: {tema.acento}; }}
    .metric-label {{
        font-size: 12.5px; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.8px; color: {tema.texto_sec}; margin-bottom: 8px;
    }}
    .metric-value {{ font-size: 32px; font-weight: 800; color: {tema.texto}; line-height: 1.1; }}
    .metric-delta {{ font-size: 12.5px; font-weight: 600; margin-top: 8px; }}
    .delta-positive {{ color: {tema.alerta}; }}
    .delta-negative {{ color: {tema.positivo}; }}
    .delta-neutral {{ color: {tema.acento}; }}

    /* ---------- Abas ---------- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px; background-color: {tema.card}; padding: 6px;
        border-radius: 12px; border: 1px solid {tema.borda};
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px; color: {tema.texto_sec};
        font-weight: 600; font-size: 13.5px; padding: 10px 18px; transition: all 0.2s;
    }}
    .stTabs [aria-selected="true"] {{
        background: linear-gradient(90deg, #5C0011, {tema.primario}) !important;
        color: {tema.cor_texto_sobre_primario} !important;
    }}

    /* ---------- Navegação por painéis e seletores (pills) ----------
       O Streamlit usa primaryColor como cor do texto do item selecionado.
       Sem esta regra, o item ativo ficaria vermelho-sangue sobre fundo
       vermelho-sangue (1,9:1) — ilegível. */
    [data-testid="stButtonGroup"] button[data-variant="pills"] {{
        background-color: transparent !important;
        color: {tema.texto_sec} !important;
        border: 1px solid {tema.borda} !important;
        transition: all 0.2s ease;
    }}
    [data-testid="stButtonGroup"] button[data-variant="pills"]:hover {{
        color: {tema.texto} !important;
        border-color: {tema.borda_forte} !important;
    }}
    [data-testid="stButtonGroup"] button[data-variant="pills"][data-selected="true"],
    [data-testid="stButtonGroup"] button[data-variant="pills"][aria-checked="true"] {{
        background: linear-gradient(90deg, #5C0011, {tema.primario}) !important;
        color: {tema.cor_texto_sobre_primario} !important;
        border-color: {tema.primario} !important;
        font-weight: 700 !important;
    }}

    /* ---------- Indicador de radio (cor primária legível) ---------- */
    [data-testid="stRadioOption"] label > div > div:first-of-type {{
        background-color: {tema.acento} !important;
    }}
    [data-testid="stRadioOption"] label > div > div:first-of-type > div {{
        background-color: {tema.fundo} !important;
    }}

    /* ---------- Tabelas ---------- */
    [data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; border: 1px solid {tema.borda}; }}

    /* ---------- Central de Alertas ---------- */
    .alert-card {{
        border-radius: 12px; padding: 14px 16px; margin-bottom: 10px;
        background: {tema.card}; border: 1px solid {tema.borda};
        border-left-width: 5px; border-left-style: solid;
    }}
    .alert-critico  {{ border-left-color: {tema.alerta}; }}
    .alert-atencao  {{ border-left-color: {tema.acento}; }}
    .alert-positivo {{ border-left-color: {tema.positivo}; }}
    .alert-info     {{ border-left-color: {tema.texto_sec}; }}
    .alert-title {{ font-size: 14.5px; font-weight: 700; color: {tema.texto}; margin: 0 0 4px 0; }}
    .alert-detail {{ font-size: 13px; color: {tema.texto}; margin: 0; line-height: 1.5; }}
    .alert-meta {{
        font-size: 11.5px; color: {tema.texto_sec}; margin-top: 6px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .alert-badge {{
        float: right; font-size: 11.5px; font-weight: 700;
        padding: 3px 9px; border-radius: 999px;
        background: {tema.borda}; color: {tema.acento};
    }}
</style>
"""
