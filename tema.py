"""Sistema de temas do dashboard — Noir Industrial (escuro) e Concreto (claro).

Fonte única de verdade das cores, dos estilos CSS e dos templates Plotly.

Objetivo
--------
Manter uma **identidade visual industrial** em dois modos de exibição, com
**contraste WCAG 2.1 AA verificado** em todos os pares de cor efetivamente usados.

Paleta Noir Industrial
----------------------
| Elemento            | Cor                | Hex       |
|---------------------|--------------------|-----------|
| Background principal| Grafite           | ``#111111``|
| Cards / Sidebar     | Cinza chumbo       | ``#1C1C1E``|
| Acento primário     | Laranja ferrugem   | ``#CC5500``|
| Acento secundário   | Ciano enferrujado  | ``#008B8B``|
| Texto principal     | Branco sujo        | ``#D4D4D4``|
| Alerta / risco      | Vermelho óxido     | ``#B22222``|
| Sucesso / positivo  | Verde petróleo     | ``#006D5B``|

Regras de acessibilidade aplicadas
----------------------------------
1. A paleta **da marca** (as 7 cores do briefing) é preservada como cor de
   *preenchimento*, borda e acento gráfico.
2. Como texto sobre fundo escuro, as cores saturadas escuras (laranja, óxido,
   petróleo) são substituídas por **variantes de luminosidade do mesmo matiz**
   (H e S preservados), que atingem ≥ 4,5:1.
3. O botão primário usa um laranja levemente mais escuro (``#C75300``) para que
   o texto branco atinja 4,5:1 — a cor da marca continua em preenchimentos.
4. Barras, bordas e demais elementos não textuais atingem ≥ 3:1 (WCAG 1.4.11),
   e faixas vizinhas de gráficos são separadas por **ΔE ≥ 19** em CIE76.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import plotly.graph_objects as go

# =====================================================================
# PALETA DA MARCA (briefing) — preenchimento, borda e acento gráfico
# =====================================================================

GRAFITE = "#111111"             # background principal
CHUMBO = "#1C1C1E"              # cards e sidebar
LARANJA_FERRUGEM = "#CC5500"    # acento primário
CIANO_ENFERRUJADO = "#008B8B"   # acento secundário
BRANCO_SUJO = "#D4D4D4"         # texto principal
VERMELHO_OXIDO = "#B22222"      # alerta / risco
VERDE_PETROLEO = "#006D5B"      # sucesso / positivo

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

    acento: str                # acento secundário (ferrugem) já com contraste válido
    acento_claro: str          # variante clara do acento (bordas finas)
    primario: str              # acento primário (fundo de botão)

    alerta: str                # óxido — falha crítica
    positivo: str              # petróleo — sucesso
    perigo: str                # óxido — risco iminente

    faixas: dict = field(default_factory=dict)   # faixas de risco
    aging: dict = field(default_factory=dict)     # faixas de aging
    rampa: tuple = ()                            # escala sequencial
    colorway: tuple = ()                         # cores distintas de séries
    grade: str = ""                              # cor das linhas de grade

    # --- paleta do relatório em PDF (fundo de papel, sempre impresso) ---
    pdf_fundo: str = "#FFFFFF"
    pdf_cartao: str = "#FFFFFF"
    pdf_cabecalho: str = "#141416"
    pdf_texto: str = "#1A1A1C"
    pdf_texto_sec: str = "#5A5A5E"
    pdf_borda: str = "#D8D8D4"
    pdf_trilho: str = "#DEDEDA"
    pdf_acento: str = "#BA4D00"
    pdf_alerta: str = "#B12222"
    pdf_positivo: str = "#006C5A"
    pdf_perigo: str = "#B12222"

    # -----------------------------------------------------------------
    # Propriedades derivadas
    # -----------------------------------------------------------------

    @property
    def cor_texto_sobre_primario(self) -> str:
        """Cor de texto sobre o fundo do botão primário."""
        return "#FFFFFF"

    def cor_sobre(self, fundo: str) -> str:
        """Escolhe entre texto claro e escuro conforme o fundo informado."""
        return self.texto if _luminancia(fundo) < 0.45 else "#141416"


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
# TEMA ESCURO — Noir Industrial
# =====================================================================

TEMA_ESCURO = Tema(
    nome="escuro",
    rotulo="Noir Industrial (escuro)",
    emoji="🌙",
    fundo=GRAFITE,
    card=CHUMBO,
    card_alto="#26262A",
    borda="rgba(212, 212, 212, 0.12)",
    borda_forte="rgba(204, 85, 0, 0.55)",
    texto=BRANCO_SUJO,
    texto_sec="#9A9AA0",
    acento="#DC5C00",           # ferrugem clareada p/ texto — 4,52:1
    acento_claro="#E8763A",
    primario="#C75300",         # laranja do botão — branco 4,50:1
    alerta="#DF5555",           # óxido clareado — 4,51:1
    positivo="#00957C",         # petróleo clareado — 4,53:1
    perigo="#DF5555",
    faixas={
        "Baixo (Janela de Ouro)": "#00957C",
        "Médio (Atenção)": "#8A8A00",
        "Alto (Risco Crítico)": "#DC5C00",
        "Extremo (Pré-Desconexão)": "#DF5555",
    },
    aging={
        "Até 30 dias": "#00957C",
        "De 31 a 60 dias": "#8A8A00",
        "De 61 a 90 dias": "#DC5C00",
        "De 91 a 120 dias": "#B85A1E",
        "Maior que 120 dias": "#DF5555",
    },
    rampa=("#4A2C1A", "#7A3200", "#B85A1E", "#E8763A", "#F0A05A"),
    colorway=("#DC5C00", "#009393", "#DF5555", "#00957C",
               "#D4D4D4", "#9A9AA0", "#E8763A", "#5A5A5E"),
    grade="rgba(212, 212, 212, 0.12)",
)

# =====================================================================
# TEMA CLARO — Concreto
# =====================================================================

TEMA_CLARO = Tema(
    nome="claro",
    rotulo="Concreto (claro)",
    emoji="☀️",
    fundo="#F2F2F0",
    card="#FFFFFF",
    card_alto="#FAFAF8",
    borda="rgba(26, 26, 28, 0.16)",
    borda_forte="rgba(186, 77, 0, 0.45)",
    texto="#1A1A1C",             # tinta grafite — 15,5:1
    texto_sec="#5A5A5E",         # 6,12:1
    acento="#BA4D00",           # ferrugem escurecida — 4,52:1
    acento_claro=LARANJA_FERRUGEM,
    primario="#BA4D00",         # branco sobre ela = 5,06:1
    alerta="#B12222",           # óxido — 6,00:1
    positivo="#006C5A",         # petróleo — 5,69:1
    perigo="#B12222",
    faixas={
        "Baixo (Janela de Ouro)": "#006C5A",
        "Médio (Atenção)": "#6B6B00",
        "Alto (Risco Crítico)": "#BA4D00",
        "Extremo (Pré-Desconexão)": "#B12222",
    },
    aging={
        "Até 30 dias": "#006C5A",
        "De 31 a 60 dias": "#6B6B00",
        "De 61 a 90 dias": "#BA4D00",
        "De 91 a 120 dias": "#8A3A00",
        "Maior que 120 dias": "#B12222",
    },
    rampa=("#EADFD2", "#D08A4A", "#CC5500", "#8A3A00", "#4A2000"),
    colorway=("#BA4D00", "#007B7B", "#B12222", "#006C5A",
               "#1A1A1C", "#5A5A5E", "#CC5500", "#8A3A00"),
    grade="rgba(26, 26, 28, 0.14)",
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

    /* Títulos em serifa */
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
    /* ---------- Campos de entrada ----------
       O Streamlit aplica a cor de fundo do tema base em um div interno de cada
       controle (role="group"). Sem estas regras, os campos ficam escuros
       mesmo no tema claro. */
    [data-testid="stSelectbox"] > div > div[role="group"],
    [data-testid="stMultiSelect"] > div > div[role="group"],
    [data-testid="stTextInputRootElement"],
    [data-testid="stNumberInputContainer"],
    [data-baseweb="select"] > div,
    [data-baseweb="base-select"] > div,
    [data-baseweb="input"] > div {{
        background-color: {tema.card_alto} !important;
        color: {tema.texto} !important;
        border-color: {tema.borda} !important;
    }}
    [data-testid="stSelectbox"] div[role="group"] input,
    [data-testid="stMultiSelect"] div[role="group"] input,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    div[role="group"] input,
    [data-baseweb="input"] input,
    textarea {{
        background-color: {tema.card_alto} !important;
        color: {tema.texto} !important;
        caret-color: {tema.acento} !important;
    }}
    ::placeholder {{ color: {tema.texto_sec} !important; opacity: 1 !important; }}
    [data-testid="stNumberInput"] button,
    [data-testid="stSelectbox"] button,
    [data-testid="stMultiSelect"] button {{
        background-color: {tema.card_alto} !important;
        color: {tema.texto_sec} !important;
    }}
    [data-testid="stSelectbox"] svg,
    [data-testid="stMultiSelect"] svg {{
        fill: {tema.texto_sec} !important;
    }}
    [data-baseweb="popover"] [role="listbox"],
    [data-baseweb="menu"] {{
        background-color: {tema.card_alto} !important;
        color: {tema.texto} !important;
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
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.45);
        backdrop-filter: blur(12px);
    }}
    .header-title {{
        font-size: 26px;
        font-weight: 800;
        letter-spacing: -0.5px;
        background: linear-gradient(90deg, {tema.acento_claro}, {tema.alerta}, {tema.acento});
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
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
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
        background: linear-gradient(90deg, #7A3200, {tema.primario}) !important;
        color: {tema.cor_texto_sobre_primario} !important;
    }}

    /* ---------- Navegação por painéis e seletores (pills) ----------
       O Streamlit usa primaryColor como cor do texto do item selecionado.
       Sem esta regra, o item ativo ficaria laranja sobre fundo laranja. */
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
        background: linear-gradient(90deg, #7A3200, {tema.primario}) !important;
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
