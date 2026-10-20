"""Relatório Executivo em PDF de página única (Prioridade Média — Plano de Ação).

Gera um PDF pronto para envio à diretoria com: KPIs macro, distribuição de
aging (MRR em risco por faixa) e Top clientes por volume de linhas suspensas.
Identificadores corporativos e dealers NÃO são incluídos (política de anonimização).
"""
import os
import io
from datetime import datetime

import pandas as pd
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from logging_config import configurar_logging
from tema import (
    BORDO_ESCURO,
    CARMESIM,
    CINZA_FERRUGEM,
    DOURADO_ENVELHECIDO,
    PERGAMINHO,
    TEMA_PADRAO,
    VERDE_MUSGO,
    VERMELHO_SANGUE,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log = configurar_logging("relatorio")

# Paleta Gótica Vitoriana (fonte única: tema.py)
NAVY = colors.HexColor(BORDO_ESCURO)            # bordô escuro
CYAN = colors.HexColor(DOURADO_ENVELHECIDO)     # dourado envelhecido
CORAL = colors.HexColor(CARMESIM)               # carmesim
AMBER = colors.HexColor(DOURADO_ENVELHECIDO)    # dourado envelhecido
GREEN = colors.HexColor(VERDE_MUSGO)            # verde musgo
SLATE = colors.HexColor(CINZA_FERRUGEM)         # cinza ferrugem
LIGHT = colors.HexColor(PERGAMINHO)             # pergaminho
CRIMSON = colors.HexColor(VERMELHO_SANGUE)      # vermelho sangue

AGING_ORDER = [
    "Até 30 dias",
    "De 31 a 60 dias",
    "De 61 a 90 dias",
    "De 91 a 120 dias",
    "Maior que 120 dias",
    "Não Informado",
]


def _fmt_brl(v: float) -> str:
    """Formata valores em reais no padrão brasileiro, sem centavos (R$ 1.234)."""
    return f"R$ {v:,.0f}".replace(",", ".")


def gerar_pdf(df: pd.DataFrame, ticket_medio: float, ref_label: str,
              caminho_saida: str | None = None,
              tema=None) -> bytes:
    """Compila KPIs e gráficos essenciais em um PDF de 1 página (A4 paisagem).

    Args:
        df: recorte de linhas a resumir.
        ticket_medio: ticket médio mensal por linha (R$).
        ref_label: rótulo do mês de referência exibido no cabeçalho.
        caminho_saida: caminho opcional para gravar o PDF.
        tema: tema de exibição (define a paleta do documento). O relatório é
            sempre impresso em **papel claro**, com contraste WCAG AA.

    Returns: bytes do PDF (também salva em caminho_saida se informado).
    """
    if df is None or df.empty:
        raise ValueError("Não há dados no recorte atual para gerar o relatório PDF.")

    # Paleta do documento (papel) — vem do tema para manter a identidade visual
    t = tema if tema is not None else TEMA_PADRAO
    NAVY = colors.HexColor(t.pdf_cabecalho)
    CYAN = colors.HexColor(t.pdf_acento)
    CORAL = colors.HexColor(t.pdf_alerta)
    AMBER = colors.HexColor(t.pdf_acento)
    GREEN = colors.HexColor(t.pdf_positivo)
    SLATE = colors.HexColor(t.pdf_texto_sec)
    LIGHT = colors.HexColor(t.pdf_borda)
    CRIMSON = colors.HexColor(t.pdf_perigo)
    PAPER = colors.HexColor(t.pdf_fundo)
    CARD = colors.HexColor(t.pdf_cartao)
    TRILHO = colors.HexColor(t.pdf_trilho)

    df = df.copy()
    total_linhas = len(df)
    total_clientes = df["CLIENTE"].nunique()
    total_inadimp = (df["STATUS"] == "INADIMPLENTE").sum()
    pct_inadimp = (total_inadimp / total_linhas * 100) if total_linhas else 0
    criticas = df[df["AGING_LIMPO"].isin(
        ["De 61 a 90 dias", "De 91 a 120 dias", "Maior que 120 dias"])].shape[0]
    pct_critico = (criticas / total_linhas * 100) if total_linhas else 0
    tempo_medio = df["TEMPO_SUSPENSAO"].mean() if total_linhas else 0
    mrr_risco = total_linhas * ticket_medio

    faixa_fin = df.groupby("FAIXA_RISCO").size().reset_index(name="LINHAS")
    faixa_fin["MRR"] = faixa_fin["LINHAS"] * ticket_medio
    mrr_ouro = faixa_fin.loc[faixa_fin["FAIXA_RISCO"] == "Baixo (Janela de Ouro)", "MRR"].sum()
    mrr_zona_fatal = faixa_fin.loc[
        faixa_fin["FAIXA_RISCO"].isin(["Alto (Risco Crítico)", "Extremo (Pré-Desconexão)"])
    ]["MRR"].sum()

    aging_counts = df["AGING_LIMPO"].value_counts()
    max_aging = aging_counts.max() if len(aging_counts) else 1

    top_clientes = (
        df.groupby("CLIENTE")
        .agg(LINHAS=("NUMTELEFONE", "count"), UF=("UF", lambda x: x.mode().iloc[0] if len(x) else "N/I"))
        .reset_index()
        .sort_values("LINHAS", ascending=False)
        .head(10)
    )

    buf = io.BytesIO()
    w, h = landscape(A4)  # 841.89 x 595.28 pt
    c = canvas.Canvas(buf, pagesize=(w, h))

    def fit(texto, max_w, font="Helvetica", size=7.5):
        """Trunca o texto para caber dentro da largura informada (em pontos)."""
        t = str(texto)
        if c.stringWidth(t, font, size) <= max_w:
            return t
        while t and c.stringWidth(t + "…", font, size) > max_w:
            t = t[:-1]
        return t.rstrip() + "…"

    # ---------- CABEÇALHO ----------
    c.setFillColor(NAVY)
    c.rect(0, h - 78, w, 78, fill=1, stroke=0)
    c.setFillColor(PAPER)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, h - 42, "Relatório Executivo — Gestão de Parque Suspenso")
    c.setFont("Helvetica", 10)
    c.setFillColor(SLATE)
    c.drawString(40, h - 60, "Monitoramento Estratégico B2B de Linhas Corporativas Suspensas")
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(CYAN)
    c.drawRightString(w - 40, h - 42, f"Referência: {ref_label}")
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 40, h - 58, f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    # ---------- GEOMETRIA ----------
    CARD_TOP = h - 105           # topo da faixa de KPI cards
    CARD_H = 58
    CARD_BOTTOM = CARD_TOP - CARD_H
    PANEL_TOP = CARD_BOTTOM - 14
    PANEL_BOTTOM = 150
    PANEL_H = PANEL_TOP - PANEL_BOTTOM

    # ---------- KPI CARDS ----------
    kpis = [
        ("Linhas Suspensas", f"{total_linhas:,}".replace(",", "."), CYAN),
        ("Clientes Afetados", f"{total_clientes:,}".replace(",", "."), NAVY),
        ("Taxa de Inadimplência", f"{pct_inadimp:.1f}%", AMBER),
        ("Aging Crítico (>60d)", f"{pct_critico:.1f}%", CORAL),
        ("Tempo Médio Suspenso", f"{tempo_medio:.0f} dias", SLATE),
        ("MRR em Risco", _fmt_brl(mrr_risco), CORAL),
    ]
    card_w = (w - 80 - 5 * 10) / 6
    for i, (titulo, valor, cor) in enumerate(kpis):
        x = 40 + i * (card_w + 10)
        c.setFillColor(colors.white)
        c.setStrokeColor(LIGHT)
        c.roundRect(x, CARD_BOTTOM, card_w, CARD_H, 8, fill=1, stroke=1)
        c.setFillColor(cor)
        c.rect(x, CARD_BOTTOM + CARD_H - 6, card_w, 6, fill=1, stroke=0)
        c.setFillColor(SLATE)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 8, CARD_BOTTOM + 30, fit(titulo.upper(), card_w - 16, "Helvetica-Bold", 7))
        c.setFillColor(cor)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x + 8, CARD_BOTTOM + 10, valor)

    # ---------- ESQUERDA: MRR em risco por faixa ----------
    painel_x, painel_w = 40, 300
    c.setFillColor(CARD)
    c.setStrokeColor(LIGHT)
    c.roundRect(painel_x, PANEL_BOTTOM, painel_w, PANEL_H, 10, fill=1, stroke=1)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(painel_x + 14, PANEL_TOP - 22, "MRR em Risco por Faixa de Aging")
    c.setFont("Helvetica", 7.5)
    c.setFillColor(SLATE)
    c.drawString(painel_x + 14, PANEL_TOP - 34, f"Ticket médio configurável: {_fmt_brl(ticket_medio)}/linha/mês")

    barras = [
        ("Baixo (Janela de Ouro)", GREEN),
        ("Médio (Atenção)", CYAN),
        ("Alto (Risco Crítico)", AMBER),
        ("Extremo (Pré-Desconexão)", CORAL),
    ]
    ly = PANEL_TOP - 56
    bar_max = 140
    for faixa, cor in barras:
        linha = faixa_fin[faixa_fin["FAIXA_RISCO"] == faixa]
        mrr = linha["MRR"].sum()
        n_linhas = linha["LINHAS"].sum()
        c.setFillColor(SLATE)
        c.setFont("Helvetica", 8)
        c.drawString(painel_x + 14, ly, f"{faixa} ({n_linhas} linhas)")
        c.setFillColor(TRILHO)
        c.roundRect(painel_x + 14, ly - 14, bar_max, 8, 4, fill=1, stroke=0)
        c.setFillColor(cor)
        frac = (mrr / mrr_risco) if mrr_risco else 0
        c.roundRect(painel_x + 14, ly - 14, max(bar_max * frac, 2), 8, 4, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(painel_x + 14 + bar_max + 8, ly - 4, _fmt_brl(mrr))
        ly -= 34
    ly -= 6
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(painel_x + 14, ly, f"Recuperável na Janela de Ouro: {_fmt_brl(mrr_ouro)}")
    c.setFillColor(CORAL)
    c.drawString(painel_x + 14, ly - 16, f"Zona irreversível (>60d): {_fmt_brl(mrr_zona_fatal)}")

    # ---------- CENTRO: Distribuição por Aging ----------
    centro_x = painel_x + painel_w + 14
    centro_w = 205
    c.setFillColor(CARD)
    c.setStrokeColor(LIGHT)
    c.roundRect(centro_x, PANEL_BOTTOM, centro_w, PANEL_H, 10, fill=1, stroke=1)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(centro_x + 14, PANEL_TOP - 22, "Distribuição por Aging")
    cores_aging = {0: GREEN, 1: CYAN, 2: AMBER, 3: AMBER, 4: CORAL, 5: SLATE}
    ly = PANEL_TOP - 48
    for faixa in AGING_ORDER:
        n = int(aging_counts.get(faixa, 0))
        if n == 0:
            continue
        cor = cores_aging[AGING_ORDER.index(faixa)]
        c.setFillColor(SLATE)
        c.setFont("Helvetica", 7.5)
        c.drawString(centro_x + 12, ly, faixa)
        c.setFillColor(TRILHO)
        c.roundRect(centro_x + 12, ly - 13, 108, 7, 3.5, fill=1, stroke=0)
        c.setFillColor(cor)
        c.roundRect(centro_x + 12, ly - 13, max(108 * (n / max_aging), 2), 7, 3.5, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawRightString(centro_x + centro_w - 12, ly - 5, f"{n} ({n / max(total_linhas, 1) * 100:.0f}%)")
        ly -= 26

    # ---------- DIREITA: Top clientes ----------
    dir_x = centro_x + centro_w + 14
    dir_w = w - dir_x - 40
    c.setFillColor(CARD)
    c.setStrokeColor(LIGHT)
    c.roundRect(dir_x, PANEL_BOTTOM, dir_w, PANEL_H, 10, fill=1, stroke=1)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(dir_x + 14, PANEL_TOP - 22, fit("Top 10 Clientes por Volume de Linhas", dir_w - 28, "Helvetica-Bold", 11))

    col_linhas_x = dir_x + dir_w - 118
    col_uf_x = dir_x + dir_w - 50
    ly = PANEL_TOP - 42
    c.setFillColor(SLATE)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(dir_x + 14, ly, "CLIENTE")
    c.drawString(col_linhas_x, ly, "LINHAS")
    c.drawString(col_uf_x, ly, "UF")
    c.setStrokeColor(LIGHT)
    c.line(dir_x + 12, ly + 9, dir_x + dir_w - 12, ly + 9)
    ly -= 20
    for _, fx in top_clientes.iterrows():
        c.setFillColor(NAVY)
        c.setFont("Helvetica", 8)
        nome_fit = fit(fx["CLIENTE"], col_linhas_x - (dir_x + 14) - 12, "Helvetica", 8)
        c.drawString(dir_x + 14, ly, nome_fit)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(col_linhas_x, ly, str(fx["LINHAS"]))
        c.drawString(col_uf_x, ly, str(fx["UF"]))
        ly -= 18

    # ---------- RODAPÉ ----------
    c.setFillColor(SLATE)
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(40, 72, "Prioridade de ação: Janela de Ouro (0-30d) — recuperação >70% nas primeiras 72h de contato.")
    c.drawString(40, 58, "Faixas 61-90d e >90d configuram zona irreversível de desconexão definitiva por inadimplência (60 a 90 dias).")
    c.setFillColor(SLATE)
    c.setFont("Helvetica", 7)
    c.drawCentredString(w / 2, 30, "Documento de uso interno para fins executivos. Dados anonimizados — identificadores corporativos removidos.")

    c.showPage()
    c.save()
    data = buf.getvalue()

    if caminho_saida:
        with open(caminho_saida, "wb") as fp:
            fp.write(data)
    log.info("Relatório PDF gerado | referência=%s | linhas=%d | MRR em risco=R$ %.2f",
             ref_label, total_linhas, mrr_risco)
    return data


if __name__ == "__main__":
    parquet = os.path.join(BASE_DIR, "parque_suspenso_tratado.parquet")
    df_teste = pd.read_parquet(parquet)
    df_teste = df_teste[df_teste["REFERENCIA"] == df_teste["REFERENCIA"].max()]
    bytes_pdf = gerar_pdf(df_teste, 45.0, df_teste["REFERENCIA_LABEL"].iloc[0],
                          os.path.join(BASE_DIR, "relatorio_teste.pdf"))
    print(f"PDF gerado: {len(bytes_pdf)} bytes | {len(df_teste)} linhas | ref {df_teste['REFERENCIA_LABEL'].iloc[0]}")
