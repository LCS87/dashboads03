import os
import re
import html
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

import app_data as ad
import rastreador as rt
from logging_config import configurar_logging, mascarar
from tema import (
    NOME_EMPRESA,
    TEMA_ESCURO,
    TEMAS,
    css_tema,
    obter_tema,
    template_plotly,
)

log = configurar_logging("app")

# Formatação monetária compartilhada entre os painéis e o PDF
def fmt_brl(valor: float) -> str:
    """Formata valores em reais no padrão brasileiro (R$ 1.234)."""
    return f"R$ {valor:,.0f}".replace(",", ".")

# Configuração da Página Streamlit
st.set_page_config(
    page_title="Cockpit Executivo | Gestão de Parque Suspenso",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= SELETOR DE TEMA =================
# Renderizado antes do CSS para que a troca de tema valha já no mesmo rerun.
with st.sidebar:
    _nomes_tema = list(TEMAS.keys())
    # Semeia o estado do widget apenas na primeira execução. Usar `default=`
    # junto com `key=` faria o Streamlit reescrever a seleção do usuário a
    # cada rerun, impedindo a troca de tema.
    if "tema_pills" not in st.session_state:
        st.session_state["tema_pills"] = st.session_state.get("tema_nome", TEMA_ESCURO.nome)
    _escolha = st.pills(
        "🎨 Tema de exibição",
        _nomes_tema,
        format_func=lambda n: f"{TEMAS[n].emoji}  {TEMAS[n].rotulo}",
        selection_mode="single",
        key="tema_pills",
        help="Alterna entre o tema Noir Industrial (escuro) e o tema Concreto (claro).",
    )
    st.session_state["tema_nome"] = _escolha if _escolha in TEMAS else TEMA_ESCURO.nome

tema = obter_tema(st.session_state.get("tema_nome", TEMA_ESCURO.nome))

# Atalhos das cores do tema para uso nos blocos HTML do app
COR_TEXTO = tema.texto
COR_TEXTO_SEC = tema.texto_sec
COR_ACENTO = tema.acento
COR_ALERTA = tema.alerta
COR_POSITIVO = tema.positivo
COR_PERIGO = tema.perigo
COR_CARD = tema.card
COR_FUNDO = tema.fundo
COR_BORDA = tema.borda
COR_BORDA_FORTE = tema.borda_forte

# Estilização CSS — gerada a partir do tema ativo
st.markdown(css_tema(tema), unsafe_allow_html=True)


def _plot(fig, **kwargs):
    """Exibe um grafico Plotly ja com o tema ativo aplicado.

    O tema e aplicado como propriedade EXPLICITA do layout (e nao apenas via
    `template`), porque o Plotly mescla o template com o template padrao e o
    padrao pode prevalecer — o que deixava os rotulos dos eixos com a cor
    clara do Plotly, invisivel no tema claro.
    """
    from tema import aplicar_tema
    return st.plotly_chart(aplicar_tema(fig, tema), **kwargs)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Colunas mínimas exigidas pela interface (evita erro obscuro em bases corrompidas)
COLUNAS_UI_OBRIGATORIAS = [
    "REFERENCIA", "REFERENCIA_LABEL", "CLIENTE", "CNPJ_FORMATADO", "NUMTELEFONE_STR",
    "UF", "AGING_LIMPO", "FAIXA_RISCO", "STATUS", "MATERIAL", "TP_SUSPENSAO",
    "TEMPO_SUSPENSAO", "QT_DIAS", "MSG_COBRANCA",
]

# Carregamento Otimizado com Caching
@st.cache_data
def load_data() -> pd.DataFrame:
    """Carrega a base tratada (Parquet com fallback para CSV) com validação estrutural.

    Se nenhum artefato tratado existir, executa o ETL automaticamente.
    Levanta `ValueError` quando a base não tem as colunas exigidas pela UI ou está vazia.
    """
    parquet_path = os.path.join(BASE_DIR, "parque_suspenso_tratado.parquet")
    csv_path = os.path.join(BASE_DIR, "parque_suspenso_tratado.csv")
    
    if os.path.exists(parquet_path):
        log.info("Carregando base tratada: %s", os.path.basename(parquet_path))
        df = pd.read_parquet(parquet_path)
    elif os.path.exists(csv_path):
        log.info("Parquet ausente; carregando CSV tratado: %s", os.path.basename(csv_path))
        df = pd.read_csv(csv_path, sep=';', encoding='utf-8-sig')
    else:
        # Fallback para rodar ETL
        log.warning("Nenhuma base tratada encontrada. Executando ETL automaticamente...")
        from etl_pipeline import run_etl
        df = run_etl()

    # Validação estrutural da base carregada
    faltantes = [c for c in COLUNAS_UI_OBRIGATORIAS if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"A base tratada não contém as colunas exigidas: {faltantes}. "
            "Exclua os arquivos tratados e reexecute `python etl_pipeline.py`."
        )
    if df.empty:
        raise ValueError("A base tratada está vazia. Reexecute `python etl_pipeline.py`.")

    df['REFERENCIA'] = pd.to_numeric(df['REFERENCIA'], errors='coerce')
    if df['REFERENCIA'].isna().any():
        raise ValueError("Existem REFERENCIA inválidas na base tratada. Reexecute o ETL.")
    df['REFERENCIA'] = df['REFERENCIA'].astype(int)
    log.info("Base carregada: %d registros | %d meses | %d clientes.",
             len(df), df['REFERENCIA_LABEL'].nunique(), df['CLIENTE'].nunique())
    return df

# Ingestão Automática de Novos Meses (Item de Alta Prioridade do Plano de Ação)
if "etl_autocheck_done" not in st.session_state:
    try:
        from etl_pipeline import refresh_if_new_months
        with st.spinner("🔄 Verificando novos arquivos mensais..."):
            base_atualizada = refresh_if_new_months()
        st.session_state["etl_autocheck_done"] = True
        if base_atualizada:
            log.info("Base atualizada com novos meses; recarregando interface.")
            st.cache_data.clear()
            st.rerun()
    except Exception as erro_check:
        log.exception("Falha na verificação automática de novos meses: %s", erro_check)
        st.session_state["etl_autocheck_done"] = True
        st.sidebar.warning("Não foi possível verificar novos meses automaticamente. Use o botão de atualização.")

try:
    df_raw = load_data()
except Exception as e:
    log.exception("Falha ao carregar os dados do dashboard: %s", e)
    st.error(
        "**Não foi possível carregar os dados do dashboard.**\n\n"
        f"Detalhe técnico: `{e}`\n\n"
        "**Como resolver:** verifique se as bases tratadas existem e reexecute o ETL "
        "(`python etl_pipeline.py`). Os detalhes completos ficaram registrados em `logs/parque_suspenso.log`."
    )
    st.stop()

# Ordenação cronológica dinâmica dos meses (funciona p/ qualquer mês novo ingerido)
_map_meses = df_raw[['REFERENCIA', 'REFERENCIA_LABEL']].drop_duplicates().sort_values('REFERENCIA')
MESES_ORDEM = _map_meses['REFERENCIA_LABEL'].tolist()

# ================= SIDEBAR: FILTROS GLOBAIS =================
with st.sidebar:
    st.markdown(f"""
        <div style="text-align: center; padding: 10px 0 20px 0;">
            <div style="font-size: 32px;">📡</div>
            <div style="font-weight: 800; font-size: 18px; color: {COR_TEXTO}; letter-spacing: -0.3px;">PARQUE SUSPENSO</div>
            <div style="font-size: 11px; color: {COR_ACENTO}; font-weight: 600;">COCKPIT EXECUTIVO B2B</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🎛️ Filtros Globais")
    
    # 1. Filtro de Referência (Mês) — ordenação cronológica dinâmica
    ref_options = ["Todos os Meses"] + MESES_ORDEM
    ref_mais_recente = MESES_ORDEM[-1] if MESES_ORDEM else "Todos os Meses"
    default_ref_idx = ref_options.index(ref_mais_recente) if ref_mais_recente in ref_options else 0
    selected_ref = st.selectbox("Mês de Referência:", ref_options, index=default_ref_idx)
    
    # 2. Filtro de UF
    uf_list = sorted(list(df_raw['UF'].unique()))
    selected_ufs = st.multiselect("Estados (UF):", uf_list, default=[])
    
    # 3. Filtro de Aging
    aging_list = sorted(list(df_raw['AGING_LIMPO'].unique()))
    selected_agings = st.multiselect("Faixa de Aging:", aging_list, default=[])
    
    # 4. Filtro de Status
    status_list = sorted(list(df_raw['STATUS'].unique()))
    selected_status = st.multiselect("Status da Suspensão:", status_list, default=[])
    
    # 5. Filtro de Material
    mat_list = sorted(list(df_raw['MATERIAL'].unique()))
    selected_mat = st.multiselect("Tipo de Material:", mat_list, default=[])
    
    # 5b. Qualidade de dados: a base tratada já vem deduplicada pelo ETL.
    # O aviso abaixo só aparece se registros idênticos forem encontrados na base
    # carregada (ex.: Parquet antigo/restaurado manualmente) — alerta defensivo.
    QUALIDADE = ad.resumo_qualidade(df_raw)
    if QUALIDADE["duplicatas_exatas"] > 0:
        _meses_duplicados = QUALIDADE["por_mes"]
        _meses_duplicados = (
            _meses_duplicados[_meses_duplicados["DUPLICADAS"] > 0]
            if not _meses_duplicados.empty else _meses_duplicados
        )
        _rotulos = ", ".join(
            f"{r.REFERENCIA_LABEL} ({int(r.DUPLICADAS)})"
            for r in _meses_duplicados.itertuples()
        )
        log.warning("Base carregada contém %d registro(s) idêntico(s): %s. "
                    "Reexecute o ETL para aplicar a deduplicação.",
                    QUALIDADE["duplicatas_exatas"], _rotulos)
        st.warning(
            f"⚠️ **Base desatualizada:** {QUALIDADE['duplicatas_exatas']:,} registros idênticos "
            f"({_rotulos}). Reexecute o ETL (`python etl_pipeline.py`) para deduplicar.".replace(",", ".")
        )

    # 6. Busca por Cliente / CNPJ / Telefone
    search_term = st.text_input("🔍 Busca (Cliente, CNPJ ou Telefone):", placeholder="Ex: 8198449... ou Crediário")
    
    st.markdown("---")
    st.markdown("### 💰 Parâmetros Financeiros")
    st.caption("Ajuste o ticket médio para projetar a receita recorrente (MRR) em risco:")
    ticket_medio = st.number_input(
        "Ticket Médio Mensal por Linha (R$):",
        min_value=10.0, max_value=300.0, value=45.0, step=5.0, format="%.2f"
    )
    
    st.markdown("---")
    st.markdown("### 🎯 Metas de Recuperação")
    meta_ouro = st.slider("Meta 0-30 dias (Janela de Ouro):", 0, 100, 60, 5, format="%d%%")
    meta_medio = st.slider("Meta 31-60 dias (Atenção):", 0, 100, 40, 5, format="%d%%")
    
    st.markdown("---")
    if st.button("🔄 Atualizar Base / Detectar Novos Meses", width='stretch'):
        with st.spinner("Verificando e reprocessando a base..."):
            try:
                from etl_pipeline import refresh_if_new_months
                atualizado = refresh_if_new_months()
                st.cache_data.clear()
                if not atualizado:
                    st.toast("Nenhum mês novo detectado. Base já está atualizada.", icon="✅")
                else:
                    st.rerun()
            except Exception as u_prob:
                st.error(f"Falha na atualização: {u_prob}")
    
    st.markdown(f"""
        <div style="font-size: 11px; color: {COR_TEXTO_SEC};">
            <b>Módulo:</b> Monitoramento & Recuperação B2B<br>
            <b>Cobertura:</b> Linhas Corporativas Ativas<br>
            <b>Atualização:</b> Base Consolidada 2026
        </div>
    """, unsafe_allow_html=True)

# Aplicação dos Filtros
# A base tratada já é deduplicada na origem pelo ETL (ver REMOVER_DUPLICATAS_EXATAS).
df_base = df_raw
df_filtered = df_base.copy()

if selected_ref != "Todos os Meses":
    df_filtered = df_filtered[df_filtered['REFERENCIA_LABEL'] == selected_ref]

if selected_ufs:
    df_filtered = df_filtered[df_filtered['UF'].isin(selected_ufs)]

if selected_agings:
    df_filtered = df_filtered[df_filtered['AGING_LIMPO'].isin(selected_agings)]

if selected_status:
    df_filtered = df_filtered[df_filtered['STATUS'].isin(selected_status)]

if selected_mat:
    df_filtered = df_filtered[df_filtered['MATERIAL'].isin(selected_mat)]

if search_term:
    term = search_term.strip().lower()
    df_filtered = df_filtered[
        df_filtered['CLIENTE'].str.lower().str.contains(term, na=False) |
        df_filtered['CNPJ_FORMATADO'].str.contains(term, na=False) |
        df_filtered['NUMTELEFONE_STR'].str.contains(term, na=False)
    ]

# ================= HEADER EXECUTIVO =================
st.markdown(f"""
<div class="header-box">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 15px;">
        <div>
            <h1 class="header-title">Cockpit Executivo: Gestão de Parque Suspenso</h1>
            <div class="header-sub">
                <span>📊 <b>Painel:</b> Monitoramento Estratégico & Recuperação de Linhas</span>
                <span>⏱️ <b>Periodicidade:</b> Acompanhamento Mensal Consolidado</span>
            </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
            <span class="header-badge">Filtro Ativo: {selected_ref}</span>
            <span class="header-badge" style="background: {COR_BORDA}; color: {COR_POSITIVO}; border-color: {COR_BORDA};">
                {len(df_filtered):,} Linhas Filtradas
            </span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Proteção contra filtros que esvaziem a base
if df_filtered.empty:
    st.warning("⚠️ Nenhuma linha encontrada com os filtros selecionados. Ajuste os filtros na sidebar para visualizar os indicadores.")
    st.stop()

# ================= NAVEGAÇÃO ENTRE PAINÉIS (Lazy Loading) =================
# Apenas o painel selecionado é renderizado — os gráficos das demais abas deixam
# de ser construídos a cada interação, reduzindo o tempo de resposta do dashboard.
PAINEIS = {
    "📊 Cockpit Executivo": "cockpit",
    "⏳ Aging & Risco de Churn": "aging",
    "🏢 Top Contas & Concentração": "contas",
    "🗺️ Inteligência Geográfica": "geo",
    "⚡ Régua de Cobrança & Ações": "regua",
    "📞 Rastreador de Recuperação": "rastreador",
}
OPCAO_TODOS = "🗂️ Todos os Painéis"

painel_escolhido = st.pills(
    "Navegação entre painéis",
    list(PAINEIS.keys()) + [OPCAO_TODOS],
    default=list(PAINEIS.keys())[0],
    selection_mode="single",
    label_visibility="collapsed",
) or list(PAINEIS.keys())[0]


def ativo(painel: str) -> bool:
    """Indica se o painel informado deve ser renderizado no momento (lazy loading)."""
    return painel_escolhido == OPCAO_TODOS or PAINEIS.get(painel_escolhido) == painel


log.info("Renderizando painel: '%s' | recorte: %s | %d linha(s)",
         painel_escolhido, selected_ref, len(df_filtered))


# ================= COMPONENTES INTERATIVOS (fragments) =================
# Fragments re-executam APENAS o próprio bloco quando seus widgets mudam,
# evitando reconstruir KPIs e gráficos de todo o dashboard (Fase 2 — UX).
@st.fragment
def ficha_cliente(df_recorte: pd.DataFrame, client_agg: pd.DataFrame) -> None:
    """Ficha detalhada de um cliente (drill-down) sem rerender global."""
    st.markdown("#### 🔎 Ficha Detalhada do Cliente (Drill-down)")
    lista_clientes = ["Selecione um cliente para auditar..."] + list(client_agg["CLIENTE"].unique())
    cliente_selecionado = st.selectbox("Selecione o Cliente:", lista_clientes, key="drill_cliente")

    if cliente_selecionado == "Selecione um cliente para auditar...":
        st.caption("Selecione um cliente para auditar as linhas suspensas do CNPJ.")
        return

    df_cliente = df_recorte[df_recorte["CLIENTE"] == cliente_selecionado]
    ca, cb, cc = st.columns(3)
    with ca:
        st.metric("Total de Linhas do Cliente", len(df_cliente))
    with cb:
        st.metric("CNPJ", df_cliente["CNPJ_FORMATADO"].iloc[0])
    with cc:
        st.metric("Média de Dias Suspenso", f"{df_cliente['TEMPO_SUSPENSAO'].mean():.1f} dias")

    st.markdown("##### Linhas Associadas:")
    st.dataframe(
        df_cliente[["NUMTELEFONE", "UF", "AGING_LIMPO", "TEMPO_SUSPENSAO",
                    "DT_SUSPENSAO", "DTPRIMEIRAATIVACAO", "STATUS", "REFERENCIA_LABEL"]],
        width="stretch",
    )


@st.fragment
def gerador_acionamento(df_recorte: pd.DataFrame) -> None:
    """Gerador de mensagem/acionamento de WhatsApp sem rerender global."""
    st.markdown("#### 📲 Gerador de Acionamento WhatsApp")
    clientes_disp = df_recorte["CLIENTE"].unique()
    if len(clientes_disp) == 0:
        st.info("Nenhum cliente disponível no recorte atual.")
        return

    sel_cli_act = st.selectbox("Selecione o Cliente para Cobrança:", clientes_disp, key="acao_cliente")
    sub_act = df_recorte[df_recorte["CLIENTE"] == sel_cli_act].iloc[0]

    # Limpar telefone e escapar HTML (evita quebra/injeção de layout com dados de cadastro)
    import urllib.parse
    import html as _html
    from etl_pipeline import sanitizar_mensagem
    tel_clean = re.sub(r"\D", "", str(sub_act.get("NUMTELEFONE_STR", "")))
    cliente_txt = _html.escape(str(sub_act["CLIENTE"]))
    cnpj_txt = _html.escape(str(sub_act.get("CNPJ_FORMATADO", "N/I")))
    uf_txt = _html.escape(str(sub_act.get("UF", "N/I")))
    tel_exibicao = _html.escape(str(sub_act.get("NUMTELEFONE", tel_clean)))
    texto_msg = str(sub_act.get("MSG_COBRANCA", ""))
    msg_exibicao = _html.escape(texto_msg).replace("\n", "<br>")
    link_wa = "https://wa.me/55{}?text={}".format(
        tel_clean, urllib.parse.quote(texto_msg)
    ) if len(tel_clean) >= 10 else None

    if link_wa:
        # Botão nativo do Streamlit: imune ao parser de Markdown e herda o tema.
        st.link_button("💬 Abrir Conversa no WhatsApp", link_wa, type="primary")
    else:
        log.warning("Cliente '%s' sem telefone válido para acionamento (tel=%s).",
                    sel_cli_act, mascarar(tel_clean) if tel_clean else "vazio")
        st.warning("⚠️ Telefone inválido/ausente — acionamento manual necessário.")

    # Cartão em LINHA ÚNICA: sem indentação e sem linha em branco no meio.
    # Em Markdown, linha indentada 4+ espaços vira bloco de código e linha em branco
    # encerra o bloco HTML — qualquer um dos dois faz o HTML aparecer como texto literal.
    cartao = (
        f'<div style="background: {COR_CARD}; padding: 20px; border-radius: 12px; '
        'border: 1px solid {COR_BORDA}; border-top: 2px solid {COR_BORDA_FORTE};">'
        f'<div style="font-weight: 700; color: {COR_ACENTO}; font-size: 16px;">{cliente_txt}</div>'
        f'<div style="color: {COR_TEXTO_SEC}; font-size: 13px; margin-bottom: 12px;">'
        f'CNPJ: {cnpj_txt} | UF: {uf_txt} | Telefone: {tel_exibicao}</div>'
        '<div style="background: {COR_FUNDO}; padding: 14px; border-radius: 8px; '
        'border-left: 3px solid {COR_ACENTO}; font-size: 13px; color: {COR_TEXTO}; margin-bottom: 15px;">'
        f'{msg_exibicao}</div></div>'
    )
    st.markdown(cartao, unsafe_allow_html=True)

@st.fragment
def registrar_acao_form(df_recorte: pd.DataFrame, acoes: pd.DataFrame) -> None:
    """Formulário de registro de ação de recuperação (fragment: não recarrega o dashboard)."""
    st.markdown("#### ➕ Registrar Ação de Recuperação")

    if df_recorte.empty:
        st.info("Nenhuma linha disponível no recorte atual para registrar ação.")
        return

    # Cliente -> linha (telefone + mês de referência)
    clientes = sorted(df_recorte["CLIENTE"].dropna().unique())
    cliente_sel = st.selectbox("Cliente (CNPJ):", clientes, key="rec_cliente")

    linhas = (
        df_recorte[df_recorte["CLIENTE"] == cliente_sel]
        [["NUMTELEFONE_STR", "REFERENCIA", "REFERENCIA_LABEL", "FAIXA_RISCO"]]
        .drop_duplicates(subset=["NUMTELEFONE_STR", "REFERENCIA"])
        .sort_values(["REFERENCIA", "NUMTELEFONE_STR"])
    )
    rotulos = {
        f"{r.NUMTELEFONE_STR} · {r.REFERENCIA_LABEL} · {r.FAIXA_RISCO}": (r.NUMTELEFONE_STR, int(r.REFERENCIA))
        for r in linhas.itertuples()
    }
    linha_sel = st.selectbox("Linha (telefone · mês · risco):", list(rotulos), key="rec_linha")
    telefone, referencia = rotulos[linha_sel]

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        canal = st.selectbox("Canal do contato:", rt.CANAIS, key="rec_canal")
    with col_c2:
        resultado = st.selectbox("Resultado do contato:", rt.RESULTADOS, key="rec_resultado")

    col_c3, col_c4 = st.columns(2)
    with col_c3:
        operador = st.text_input("Operador responsável:", key="rec_operador",
                                 placeholder="Ex: Ana Souza")
    with col_c4:
        dt_retorno = st.date_input("Próximo retorno (opcional):", value=None, key="rec_retorno")

    observacao = st.text_area("Observação:", key="rec_obs", height=70,
                              placeholder="Ex: cliente informou que fará o pagamento até sexta-feira")

    if st.button("💾 Registrar ação", type="primary", width='stretch', key="rec_salvar"):
        try:
            registro = rt.registrar_acao(
                numtelefone=telefone, referencia=referencia, canal=canal,
                resultado=resultado, operador=operador, cliente=cliente_sel,
                observacao=observacao, dt_retorno=dt_retorno,
            )
            # Flash message: sobrevive ao rerun porque é lida no início do painel
            st.session_state["_rec_flash"] = (
                f"Ação {registro['ID_ACAO']} registrada com sucesso para a linha "
                f"{mascarar(telefone)} ({resultado} · {canal})."
            )
            st.rerun(scope="app")
        except rt.AcaoInvalidaError as erro_validacao:
            st.error(f"Não foi possível registrar: {erro_validacao}")
        except Exception as erro:
            log.exception("Falha ao registrar ação de recuperação: %s", erro)
            st.error("Erro inesperado ao registrar a ação. Consulte `logs/parque_suspenso.log`.")

    if not acoes.empty:
        st.caption("🕒 Últimas ações registradas")
        st.dataframe(
            acoes.sort_values("DT_ACAO", ascending=False)
            .head(5)[["ID_ACAO", "DT_ACAO", "NUMTELEFONE", "RESULTADO", "CANAL", "OPERADOR"]],
            width="stretch", hide_index=True,
        )


# ================= PAINEL 1: COCKPIT EXECUTIVO =================
if ativo("cockpit"):
    # KPIs macro (agregação cacheada — Fase 2)
    kpis = ad.resumo_kpis(df_filtered)
    total_linhas = kpis["total_linhas"]
    total_clientes = kpis["total_clientes"]
    total_inadimp = kpis["total_inadimp"]
    pct_inadimp = kpis["pct_inadimp"]
    linhas_criticas = kpis["linhas_criticas"]
    pct_critico = kpis["pct_critico"]
    tempo_medio = kpis["tempo_medio"]
    
    # 💰 Estimativa de Impacto Financeiro (MRR em Risco) — Item Alta Prioridade
    mrr_risco = total_linhas * ticket_medio
    mrr_risco_ano = mrr_risco * 12
    
    # Variação MoM (se um único mês estiver selecionado) — ordem cronológica dinâmica
    delta_linhas_str = "Visão Geral Consolidada"
    delta_class = "delta-neutral"
    
    if selected_ref != "Todos os Meses":
        if selected_ref in MESES_ORDEM:
            idx = MESES_ORDEM.index(selected_ref)
            if idx > 0:
                mes_anterior = MESES_ORDEM[idx - 1]
                linhas_anterior = len(df_base[df_base['REFERENCIA_LABEL'] == mes_anterior])
                linhas_atual = len(df_base[df_base['REFERENCIA_LABEL'] == selected_ref])
                diff = linhas_atual - linhas_anterior
                diff_pct = (diff / linhas_anterior * 100) if linhas_anterior > 0 else 0
                if diff > 0:
                    delta_linhas_str = f"▲ +{diff:,} (+{diff_pct:.1f}%) vs {mes_anterior}"
                    delta_class = "delta-positive" # Aumento de suspensão é negativo
                else:
                    delta_linhas_str = f"▼ {diff:,} ({diff_pct:.1f}%) vs {mes_anterior}"
                    delta_class = "delta-negative" # Queda de suspensão é positivo
    
    # Grid de KPIs (6 cartões: + MRR em Risco)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Linhas Suspensas</div>
            <div class="metric-value" style="color: {COR_ACENTO};">{total_linhas:,}</div>
            <div class="metric-delta {delta_class}">{delta_linhas_str}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Clientes Afetados</div>
            <div class="metric-value">{total_clientes:,}</div>
            <div class="metric-delta delta-neutral">CNPJs / Contratos B2B</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Taxa Inadimplência</div>
            <div class="metric-value" style="color: {COR_ACENTO};">{pct_inadimp:.1f}%</div>
            <div class="metric-delta delta-neutral">{total_inadimp:,} linhas em débito</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Aging Crítico (&gt;60d)</div>
            <div class="metric-value" style="color: {COR_ALERTA};">{pct_critico:.1f}%</div>
            <div class="metric-delta delta-positive">{linhas_criticas:,} em risco iminente</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Tempo Médio Suspenso</div>
            <div class="metric-value" style="color: {COR_PERIGO};">{tempo_medio:.0f} <span style="font-size: 16px;">dias</span></div>
            <div class="metric-delta delta-neutral">Por linha bloqueada</div>
        </div>
        """, unsafe_allow_html=True)

    with c6:
        st.markdown(f"""
        <div class="metric-card" style="border-bottom: 3px solid {COR_ALERTA};">
            <div class="metric-label">💰 MRR em Risco</div>
            <div class="metric-value" style="color: {COR_ALERTA}; font-size: 27px;">{fmt_brl(mrr_risco)}</div>
            <div class="metric-delta delta-positive">Ticket {fmt_brl(ticket_medio)}/linha · {fmt_brl(mrr_risco_ano)}/ano</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)

    # 🔎 Integridade da base (defensivo: a base tratada já vem deduplicada do ETL)
    if QUALIDADE["duplicatas_exatas"] > 0:
        with st.expander(f"⚠️ Base desatualizada: {QUALIDADE['duplicatas_exatas']:,} registros idênticos".replace(",", ".")):
            st.markdown(
                "A base carregada contém **linhas 100% idênticas**, normalmente resultado de "
                "**carga duplicada do arquivo de origem** — o que infla os KPIs do período. "
                "O pipeline de ETL já remove esses registros automaticamente.\n\n"
                "**Ação necessária:** reexecutar o ETL (`python etl_pipeline.py`) para regenerar "
                "a base tratada deduplicada."
            )
            st.dataframe(QUALIDADE["por_mes"], width='stretch')
    
    # Gráficos da Visão Geral
    col_chart1, col_chart2 = st.columns([1.6, 1])
    
    with col_chart1:
        st.markdown(f"#### 📈 Evolução Histórica do Parque Suspenso ({MESES_ORDEM[0]} - {MESES_ORDEM[-1]})")
        
        # Agrupamento temporal (cacheado — Fase 2)
        hist_df = ad.historico_mensal(df_base)
        
        fig_hist = px.bar(
            hist_df,
            x='REFERENCIA_LABEL',
            y='CONTAGEM',
            color='STATUS',
            title=None,
            barmode='stack',
            color_discrete_map={
                'INADIMPLENTE': tema.perigo,
                'SUSPENSAO PARCIAL POR FRAUDE': tema.alerta,
                'SUSPENSAO TOTAL POR PERDA/ROUBO': tema.acento,
                'SUSPENSAO A PEDIDO': tema.positivo
            }
        )
        fig_hist.update_layout(
            template=template_plotly(tema),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=20, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified"
        )
        # Anotação dinâmica apenas quando o volume de um mês é anomalamente alto
        # (ex.: >1,5x a média). Com a base deduplicada, o falso pico de Abr/2026 não aparece.
        totais_mes = hist_df.groupby('REFERENCIA_LABEL')['CONTAGEM'].sum()
        if len(totais_mes) >= 2 and totais_mes.max() > totais_mes.mean() * 1.5:
            mes_pico = totais_mes.idxmax()
            pico_val = int(totais_mes.max())
            fig_hist.add_annotation(
                x=mes_pico,
                y=pico_val,
                text=f"Pico de Volume ({pico_val:,} linhas)".replace(",", "."),
                showarrow=True,
                arrowhead=2,
                arrowcolor=tema.alerta,
                arrowsize=1,
                arrowwidth=2,
                ax=0,
                ay=-40,
                font=dict(size=11, color=tema.alerta),
                bgcolor=tema.card,
                bordercolor=tema.alerta
            )
        _plot(fig_hist, width='stretch')
        
    with col_chart2:
        st.markdown("#### 🍩 Distribuição por Faixa de Aging")
        aging_counts = ad.contagens(df_filtered, 'AGING_LIMPO')
        aging_counts.columns = ['AGING', 'CONTAGEM']
        
        # Cores para cada aging (rampa Gótica Vitoriana, definida em tema.py)
        aging_colors = tema.aging
        
        fig_donut = px.pie(
            aging_counts,
            values='CONTAGEM',
            names='AGING',
            hole=0.55,
            color='AGING',
            color_discrete_map=aging_colors
        )
        fig_donut.update_traces(
            textposition='inside',
            textinfo='percent+label',
            marker=dict(line=dict(color=tema.card, width=2))
        )
        fig_donut.update_layout(
            template=template_plotly(tema),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=10)
        )
        _plot(fig_donut, width='stretch')

    # Segunda Linha: Tipo de Material e Tipo de Suspensão
    col_mat, col_tipo = st.columns(2)
    with col_mat:
        st.markdown("#### 📱 Distribuição por Material / Dispositivo")
        mat_counts = ad.contagens(df_filtered, 'MATERIAL')
        fig_mat = px.bar(
            mat_counts,
            x='CONTAGEM',
            y='MATERIAL',
            orientation='h',
            text='CONTAGEM',
            color='MATERIAL',
            color_discrete_sequence=list(tema.colorway[:3])
        )
        fig_mat.update_layout(
            template=template_plotly(tema),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0)
        )
        _plot(fig_mat, width='stretch')

    with col_tipo:
        st.markdown("#### 🔒 Severidade: Suspensão Parcial vs. Total")
        tp_counts = ad.contagens(df_filtered, 'TP_SUSPENSAO')
        fig_tp = px.bar(
            tp_counts,
            x='CONTAGEM',
            y='TP_SUSPENSAO',
            orientation='h',
            text='CONTAGEM',
            color='TP_SUSPENSAO',
            color_discrete_sequence=list(tema.colorway[:2])
        )
        fig_tp.update_layout(
            template=template_plotly(tema),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0)
        )
        _plot(fig_tp, width='stretch')

    # ================= 🚨 CENTRAL DE ALERTAS =================
    st.markdown("---")
    st.markdown("### 🚨 Central de Alertas")
    st.markdown("""
    > Sinais automáticos sobre a evolução do parque. Cada alerta mostra **a regra que o
    > disparou** — nada de caixa preta.
    """)

    alertas_painel = ad.alertas_do_painel(df_base, ticket_medio)

    _cor_alerta = {"critico": "alert-critico", "atencao": "alert-atencao",
                   "positivo": "alert-positivo", "info": "alert-info"}
    _cor_hex = {"critico": tema.alerta, "atencao": tema.acento,
                "positivo": tema.positivo, "info": tema.texto_sec}
    _icone_alerta = {"critico": "🔴", "atencao": "🟠", "positivo": "🟢", "info": "🔵"}
    _rotulo_alerta = {"critico": "Crítico", "atencao": "Atenção",
                      "positivo": "Positivo", "info": "Informativo"}

    if not alertas_painel:
        st.success("✅ Nenhum alerta no período. Todos os indicadores monitorados estão dentro dos limites.")
    else:
        contagem = {nivel: sum(1 for a in alertas_painel if a["nivel"] == nivel)
                    for nivel in ["critico", "atencao", "positivo", "info"]}
        ca, cb, cc, cd = st.columns(4)
        for coluna, nivel in zip([ca, cb, cc, cd], ["critico", "atencao", "positivo", "info"]):
            with coluna:
                st.markdown(f"""
                <div class="metric-card" style="border-bottom: 3px solid {_cor_hex[nivel]};">
                    <div class="metric-label">{_icone_alerta[nivel]} {_rotulo_alerta[nivel]}</div>
                    <div class="metric-value" style="color: {_cor_hex[nivel]};">{contagem[nivel]}</div>
                </div>
                """, unsafe_allow_html=True)

        for alerta in alertas_painel:
            st.markdown(f"""
            <div class="alert-card {_cor_alerta[alerta['nivel']]}">
                <span class="alert-badge">{html.escape(alerta['valor'])}</span>
                <p class="alert-title">{_icone_alerta[alerta['nivel']]} {html.escape(alerta['titulo'])}</p>
                <p class="alert-detail">{html.escape(alerta['detalhe'])}</p>
                <p class="alert-meta">regra: {html.escape(alerta['regra'])}</p>
            </div>
            """, unsafe_allow_html=True)

    # ================= 📈 TENDÊNCIAS E VARIAÇÃO MENSAL =================
    st.markdown("---")
    st.markdown("### 📈 Tendências e Variação Mensal")

    serie = ad.serie_mensal(df_base, ticket_medio)

    if serie.empty:
        st.info("Sem dados suficientes para análise de tendência.")
    else:
        col_graf, col_tab = st.columns([1.3, 1])

        with col_graf:
            fig_tend = go.Figure()
            fig_tend.add_bar(
                x=serie["REFERENCIA_LABEL"], y=serie["LINHAS"],
                name="Linhas no mês", marker_color=tema.acento,
                text=serie["LINHAS"], textposition="outside",
            )
            fig_tend.add_scatter(
                x=serie["REFERENCIA_LABEL"], y=serie["MM3"],
                name="Média móvel (3 meses)", mode="lines+markers",
                line=dict(color=tema.acento, width=3, dash="dot"),
            )
            fig_tend.update_layout(
                template=template_plotly(tema), paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)', height=380,
                margin=dict(l=0, r=0, t=30, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                yaxis_title="Linhas suspensas",
            )
            _plot(fig_tend, width='stretch')

        with col_tab:
            tabela_tend = serie[[
                "REFERENCIA_LABEL", "LINHAS", "VAR_MOM_%", "CLIENTES",
                "PCT_CRITICO", "MRR_RISCO",
            ]].rename(columns={
                "REFERENCIA_LABEL": "Mês", "LINHAS": "Linhas", "VAR_MOM_%": "Variação (%)",
                "CLIENTES": "Clientes", "PCT_CRITICO": "Crítico (%)", "MRR_RISCO": "MRR Risco",
            })
            st.dataframe(
                tabela_tend, width='stretch', hide_index=True,
                column_config={
                    "Variação (%)": st.column_config.NumberColumn(format="%+.1f%%"),
                    "Crítico (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "MRR Risco": st.column_config.NumberColumn(format="R$ %d"),
                },
            )
            if len(serie) >= 2:
                atual, anterior = serie.iloc[-1], serie.iloc[-2]
                delta = atual["LINHAS"] - anterior["LINHAS"]
                sinal = "alta" if delta > 0 else ("queda" if delta < 0 else "estabilidade")
                st.caption(
                    f"De **{anterior['REFERENCIA_LABEL']}** para **{atual['REFERENCIA_LABEL']}**: "
                    f"{sinal} de **{abs(delta):,.0f}** linha(s) "
                    f"({atual['VAR_MOM_%']:+.1f}%)."
                )

    # ================= 📊 EVOLUÇÃO DO AGING POR MÊS =================
    with st.expander("📊 Evolução da composição de aging por mês (e o achado de Abr/2026)"):
        st.markdown("""
        Percentual de linhas em cada faixa de aging, mês a mês. **Atenção a Abr/2026.**
        """)
        composicao = (
            pd.crosstab(df_base["REFERENCIA_LABEL"], df_base["AGING_LIMPO"], normalize="index") * 100
        ).round(1)
        ordem_meses = df_base.sort_values("REFERENCIA")["REFERENCIA_LABEL"].drop_duplicates().tolist()
        composicao = composicao.reindex(ordem_meses)
        st.dataframe(composicao, width='stretch')

        st.markdown("""
        > ⚠️ **Achado de qualidade de dados:** o bloco de **Abr/2026** teve a coluna de tempo
        > suspenso calculada em **22/06/2026** (82 dias após o mês de referência), enquanto
        > os demais meses foram extraídos dentro do próprio mês (3 a 12 dias). Por isso
        > Abril aparece com ~92% de aging crítico e os outros meses com ~4% a 15% — **não é
        > um evento de negócio, é inconsistência de extração**. O aging, a criticidade e o
        > MRR em risco de Abril **não são comparáveis** com os demais meses.
        >
        > **O que fazer:** solicitar à origem a reextração corrigida do bloco de Abril ou
        > ativar `NORMALIZAR_AGING_POR_REFERENCIA = True` em `etl_pipeline.py` para recalcular
        > o aging a partir de `DT_SUSPENSAO` (o campo confiável). Veja `ANALISE_E_PLANO_DE_MELHORIAS.md`.
        """)

# ================= PAINEL 2: AGING & RISCO DE CHURN =================
if ativo("aging"):
    st.markdown("### ⏳ Matriz de Aging & Risco de Desconexão Involuntária")
    st.markdown("""
    > Linhas suspensas por mais de **60 a 90 dias** entram na zona irreversível de cancelamento definitivo (churn involuntário).
    """)
    
    # Cartões por faixa de risco (contagens cacheadas — Fase 2)
    faixas_risco = ad.contagem_faixa_risco(df_filtered)
    q_ouro = faixas_risco['Baixo (Janela de Ouro)']
    q_medio = faixas_risco['Médio (Atenção)']
    q_alto = faixas_risco['Alto (Risco Crítico)']
    q_extremo = faixas_risco['Extremo (Pré-Desconexão)']

    # 4 Cartões de Risco
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid {COR_POSITIVO};">
            <div class="metric-label" style="color: {COR_POSITIVO};">🟢 Janela de Ouro (0-30d)</div>
            <div class="metric-value">{q_ouro:,}</div>
            <div class="metric-delta delta-neutral">Alta recuperabilidade</div>
        </div>
        """, unsafe_allow_html=True)
        
    with r2:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid {COR_ACENTO};">
            <div class="metric-label" style="color: {COR_ACENTO};">🟡 Atenção (31-60d)</div>
            <div class="metric-value">{q_medio:,}</div>
            <div class="metric-delta delta-neutral">Risco moderado de churn</div>
        </div>
        """, unsafe_allow_html=True)
        
    with r3:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid {COR_ACENTO};">
            <div class="metric-label" style="color: {COR_ACENTO};">🔴 Risco Crítico (61-90d)</div>
            <div class="metric-value">{q_alto:,}</div>
            <div class="metric-delta delta-positive">Última janela de quitação</div>
        </div>
        """, unsafe_allow_html=True)
        
    with r4:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid {COR_ALERTA};">
            <div class="metric-label" style="color: {COR_ALERTA};">🟣 Pré-Desconexão (>90d)</div>
            <div class="metric-value">{q_extremo:,}</div>
            <div class="metric-delta delta-positive">Cancelamento iminente</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # 💰 Impacto Financeiro por Faixa de Risco (Ticket Médio configurável — cacheado)
    st.markdown(f"#### 💰 MRR em Risco por Faixa de Risco (Ticket Médio: {fmt_brl(ticket_medio)}/linha)")
    faixa_fin = ad.financeiro_por_faixa(df_filtered, ticket_medio)

    fig_mrr = px.bar(
        faixa_fin,
        x='FAIXA_RISCO',
        y='MRR_RISCO',
        text='MRR_LABEL',
        color='FAIXA_RISCO',
        color_discrete_map={
            'Baixo (Janela de Ouro)': tema.faixas['Baixo (Janela de Ouro)'],
            'Médio (Atenção)': tema.faixas['Médio (Atenção)'],
            'Alto (Risco Crítico)': tema.faixas['Alto (Risco Crítico)'],
            'Extremo (Pré-Desconexão)': tema.faixas['Extremo (Pré-Desconexão)']
        },
        labels={'FAIXA_RISCO': 'Faixa de Aging', 'MRR_RISCO': 'MRR em Risco (R$)'}
    )
    fig_mrr.update_layout(
        template=template_plotly(tema),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    _plot(fig_mrr, width='stretch')

    mrr_recup_ouro = faixa_fin.loc[faixa_fin['FAIXA_RISCO'] == 'Baixo (Janela de Ouro)', 'MRR_RISCO'].sum()
    f1, f2 = st.columns(2)
    with f1:
        st.markdown(f"""
        <div class="metric-card" style="border-left: 4px solid {COR_POSITIVO};">
            <div class="metric-label">Dinheiro Recuperável na Janela de Ouro</div>
            <div class="metric-value" style="color: {COR_POSITIVO}; font-size: 26px;">{fmt_brl(mrr_recup_ouro)}</div>
            <div class="metric-delta delta-neutral">Faixa 0-30d · maior taxa de reversão (&gt;70%)</div>
        </div>
        """, unsafe_allow_html=True)
    with f2:
        mrr_pre_desconexao = faixa_fin.loc[faixa_fin['FAIXA_RISCO'].isin(['Alto (Risco Crítico)', 'Extremo (Pré-Desconexão)']), 'MRR_RISCO'].sum()
        st.markdown(f"""
        <div class="metric-card" style="border-left: 4px solid {COR_ALERTA};">
            <div class="metric-label">MRR em Zona Irreversível (&gt;60d)</div>
            <div class="metric-value" style="color: {COR_ALERTA}; font-size: 26px;">{fmt_brl(mrr_pre_desconexao)}</div>
            <div class="metric-delta delta-positive">Risco de baixa definitiva pela operadora</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 🎯 Painel de Metas & SLA de Recuperação (Item Prioridade Média)
    st.markdown("#### 🎯 Metas & SLA de Recuperação do Mês")
    st.caption("Proxy de recuperação: redução MoM (linhas que saíram da faixa) em relação à meta definida na sidebar.")
    idx_mes = MESES_ORDEM.index(selected_ref) if selected_ref in MESES_ORDEM else -1
    if idx_mes > 0:
        mes_ant = MESES_ORDEM[idx_mes - 1]
        df_ant = df_base[df_base['REFERENCIA_LABEL'] == mes_ant]
        cols_meta = st.columns(2)
        alvos_meta = [
            ('Baixo (Janela de Ouro)', meta_ouro, '🟢 0-30 dias'),
            ('Médio (Atenção)', meta_medio, '🟡 31-60 dias')
        ]
        for i, (faixa, meta_pct, label) in enumerate(alvos_meta):
            prev_n = (df_ant['FAIXA_RISCO'] == faixa).sum()
            cur_n = (df_filtered[df_filtered['REFERENCIA_LABEL'] == selected_ref]['FAIXA_RISCO'] == faixa).sum()
            feito = max(0, prev_n - cur_n)
            pct_realizado = (feito / prev_n * 100) if prev_n > 0 else 0
            batida_class = tema.positivo if pct_realizado >= meta_pct else tema.acento
            with cols_meta[i]:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-label">{label} — Meta {meta_pct}% ({mes_ant} → {selected_ref})</div>
                        <div class="metric-value" style="color: {batida_class}; font-size: 26px;">{pct_realizado:.1f}%</div>
                        <div class="metric-delta delta-neutral">{feito:,} linhas normalizadas de {prev_n:,} anteriores</div>
                    </div>
                    """, unsafe_allow_html=True)
                st.progress(min(pct_realizado / 100, 1.0) if meta_pct == 0 else min(pct_realizado / max(meta_pct, 1), 1.0),
                            text=f"{pct_realizado:.0f}% realizado vs meta de {meta_pct}%")
    else:
        st.info("ℹ️ Selecione um mês específico (com mês anterior na base) para acompanhar as metas de normalização MoM.")

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    st.markdown("#### 🔍 Dispersão: Tempo de Vida do Cliente (`QT_DIAS`) x Dias em Suspensão (`TEMPO_SUSPENSAO`)")
    
    fig_scatter = px.scatter(
        df_filtered,
        x='QT_DIAS',
        y='TEMPO_SUSPENSAO',
        color='FAIXA_RISCO',
        hover_data=['CLIENTE', 'NUMTELEFONE', 'UF', 'STATUS', 'DTPRIMEIRAATIVACAO'],
        color_discrete_map={
            'Baixo (Janela de Ouro)': tema.faixas['Baixo (Janela de Ouro)'],
            'Médio (Atenção)': tema.faixas['Médio (Atenção)'],
            'Alto (Risco Crítico)': tema.faixas['Alto (Risco Crítico)'],
            'Extremo (Pré-Desconexão)': tema.faixas['Extremo (Pré-Desconexão)']
        },
        labels={
            'QT_DIAS': 'Idade da Linha desde a Ativação (Dias)',
            'TEMPO_SUSPENSAO': 'Tempo Consecutivo Suspenso (Dias)'
        }
    )
    # Linha de corte em 60 dias de suspensão
    fig_scatter.add_hline(
        y=60,
        line_dash="dash",
        line_color=tema.acento,
        annotation_text="Limiar de Risco Crítico (60 dias)",
        annotation_position="bottom right"
    )
    fig_scatter.update_layout(
        template=template_plotly(tema),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=480
    )
    _plot(fig_scatter, width='stretch')

    # Tabela com as linhas mais críticas
    st.markdown("#### 🚨 Linhas com Maior Tempo em Suspensão (Ação Imediata Requerida)")
    top_criticas = df_filtered.sort_values(by='TEMPO_SUSPENSAO', ascending=False)[
        ['CLIENTE', 'CNPJ_FORMATADO', 'NUMTELEFONE', 'UF', 'AGING_LIMPO', 'TEMPO_SUSPENSAO', 'QT_DIAS', 'STATUS', 'REFERENCIA_LABEL']
    ].head(15)
    st.dataframe(top_criticas, width='stretch')

    # ================= 🤖 PROPENSÃO DE RECUPERAÇÃO (MODELO PREDITIVO) =================
    st.markdown("---")
    st.markdown("### 🤖 Propensão de Recuperação (Modelo Preditivo)")
    st.markdown("""
    > Estima a probabilidade de cada linha **sair do parque suspenso no próximo mês**
    > (proxy de reativação por pagamento). Serve para **priorizar a fila de acionamento** —
    > não como probabilidade individual precisa.
    """)

    analise = ad.propensao_recuperacao(df_base)

    if analise["metricas"].get("motivo"):
        st.info(f"ℹ️ {analise['metricas']['motivo']}")
    else:
        met = analise["metricas"]
        auc_cv = met["auc_cv"]
        auc_hold = met["auc_holdout"]
        taxa_esperada = met["taxa_esperada_alvo"]
        linhas_alvo = len(analise["scores"])
        saidas_esperadas = linhas_alvo * taxa_esperada

        # ---------- KPIs de qualidade do modelo ----------
        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            cor_auc = tema.positivo if (auc_cv or 0) >= 0.70 else (tema.acento if (auc_cv or 0) >= 0.60 else tema.alerta)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Poder Discriminante (AUC)</div>
                <div class="metric-value" style="color: {cor_auc};">{auc_cv:.3f}</div>
                <div class="metric-delta delta-neutral">validação cruzada por mês</div>
            </div>
            """, unsafe_allow_html=True)
        with mc2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">AUC (último mês)</div>
                <div class="metric-value">{auc_hold:.3f}</div>
                <div class="metric-delta delta-neutral">holdout temporal</div>
            </div>
            """, unsafe_allow_html=True)
        with mc3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Linhas Rotuladas</div>
                <div class="metric-value" style="color: {COR_ACENTO};">{met['n_rotulados']:,}</div>
                <div class="metric-delta delta-neutral">{met['n_features']} features · {met['iteracoes']} iterações</div>
            </div>
            """, unsafe_allow_html=True)
        with mc4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Saídas Esperadas no Mês</div>
                <div class="metric-value" style="color: {COR_POSITIVO};">≈ {saidas_esperadas:,.0f}</div>
                <div class="metric-delta delta-neutral">{taxa_esperada*100:.1f}% de {linhas_alvo:,} linhas</div>
            </div>
            """, unsafe_allow_html=True)

        st.caption(
            f"**Como ler:** AUC 1,0 = ordenação perfeita · 0,5 = aleatória. Este modelo está em "
            f"**{auc_cv:.2f}** (CV) — ou seja, **ordena melhor que o acaso, mas com poder moderado**. "
            "Use a fila abaixo como prioridade de trabalho, não como garantia."
        )

        # ---------- Fila priorizada + validação por tercil ----------
        st.markdown("#### 🎯 Fila Priorizada de Acionamento")
        telefones_recorte = set(df_filtered["NUMTELEFONE_STR"].astype(str))
        fila = analise["scores"][
            analise["scores"]["NUMTELEFONE_STR"].isin(telefones_recorte)
        ].copy()

        col_fila, col_val = st.columns([1.35, 1])

        with col_fila:
            if fila.empty:
                mes_alvo = analise["scores"]["REFERENCIA_LABEL"].iloc[0]
                st.caption(
                    f"O modelo pontua sempre o **mês mais recente da base** ({mes_alvo}). "
                    "Ajuste o filtro de mês na barra lateral para ver a fila."
                )
            else:
                fila_exibir = fila.head(15).copy()
                fila_exibir["PROPENSÃO (%)"] = (fila_exibir["PROB"] * 100).round(1)
                fila_exibir = fila_exibir[
                    ["CLIENTE", "NUMTELEFONE_STR", "UF", "AGING_LIMPO",
                     "TEMPO_SUSPENSAO", "MESES_CONSECUTIVOS", "PROPENSÃO (%)", "FAIXA_PROPENSAO"]
                ].rename(columns={
                    "NUMTELEFONE_STR": "Telefone", "AGING_LIMPO": "Aging",
                    "TEMPO_SUSPENSAO": "Dias Suspenso", "MESES_CONSECUTIVOS": "Meses no Parque",
                    "FAIXA_PROPENSAO": "Prioridade",
                })
                st.dataframe(
                    fila_exibir, width='stretch', hide_index=True,
                    column_config={
                        "PROPENSÃO (%)": st.column_config.ProgressColumn(
                            "Propensão", min_value=0.0, max_value=100.0, format="%.1f%%"
                        )
                    },
                )
                st.caption(
                    f"{len(fila):,} linha(s) no recorte · top 15 exibido. "
                    f"Total no mês pontuado: {linhas_alvo:,}."
                )

        with col_val:
            st.markdown("**✅ Validação por tercil** (mês de teste)")
            calibracao = analise["calibracao"][
                ["FAIXA_PROPENSAO", "LINHAS", "SAIRAM", "TAXA_OBSERVADA_%", "LIFT"]
            ].rename(columns={
                "FAIXA_PROPENSAO": "Faixa", "SAIRAM": "Saíram",
                "TAXA_OBSERVADA_%": "Saída Real (%)", "LIFT": "Lift",
            })
            st.dataframe(calibracao, width='stretch', hide_index=True)
            if not analise["calibracao"].empty:
                lift_topo = analise["calibracao"].iloc[0]["LIFT"]
                taxa_topo = analise["calibracao"].iloc[0]["TAXA_OBSERVADA_%"]
                taxa_baixo = analise["calibracao"].iloc[-1]["TAXA_OBSERVADA_%"]
                st.caption(
                    f"No tercil de maior prioridade, **{taxa_topo:.1f}%** das linhas saíram "
                    f"({lift_topo:.2f}× a média do mês) contra **{taxa_baixo:.1f}%** no menor."
                )

        # ---------- Validação por mês + fatores ----------
        st.markdown("#### 🔍 Transparência do Modelo")
        col_vm, col_cf = st.columns([1, 1.25])

        with col_vm:
            st.markdown("**AUC por mês (deixar-um-mês-de-fora)**")
            st.dataframe(
                analise["validacao"].rename(columns={
                    "REFERENCIA_LABEL": "Mês", "TAXA_SAIDA_%": "Saída Real (%)",
                }),
                width='stretch', hide_index=True,
            )

        with col_cf:
            st.markdown("**Fatores que mais influenciam** (peso padronizado)")
            fatores = analise["coeficientes"].head(8).copy()
            fig_fatores = px.bar(
                fatores.sort_values("PESO"),
                x="PESO", y="FEATURE", orientation="h",
                color="PESO", color_continuous_scale=list(tema.rampa),
                labels={"PESO": "Impacto na chance de saída", "FEATURE": ""},
            )
            fig_fatores.update_layout(
                template=template_plotly(tema), paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)', showlegend=False, coloraxis_showscale=False,
                margin=dict(l=0, r=10, t=10, b=0), height=300,
            )
            _plot(fig_fatores, width='stretch')

        with st.expander("📖 Como o modelo funciona e quais são os limites"):
            st.markdown(f"""
**Rótulo:** uma linha é marcada como "saiu" (1) quando aparece no mês M e **não** aparece em M+1.
É o único sinal objetivo de reativação disponível na base.

**Features (todas conhecidas no mês M):**

| Feature | Leitura |
|---|---|
| `TEMPO_SUSPENSAO` | Dias de suspensão — quanto maior, **menor** a chance de saída |
| `DIAS_DESDE_ATIVACAO` | Tenure da linha |
| `MESES_CONSECUTIVOS` | Meses seguidos no parque suspenso |
| `AGING_LIMPO` / `STATUS` | Faixa de aging e motivo da suspensão |

**Modelo:** regressão logística com regularização L2, implementada em NumPy puro
(sem dependência adicional). Convergência por Newton-Raphson.

**Validação:** cruzada *leave-one-month-out* — cada mês é testado uma vez com os
outros meses no treino (métrica principal: **AUC média = {auc_cv:.3f}**, faixa
{met['auc_cv_min']:.2f}–{met['auc_cv_max']:.2f}). O holdout temporal (último mês)
alimenta a tabela de calibração.

**Calibração:** as probabilidades são reescalonadas para que a média coincida com a
taxa de saída do mês mais recente ({taxa_esperada*100:.1f}%). Isso corrige a
superconfiança típica de amostras pequenas.

**Limites que você deve conhecer:**
- "Saiu do parque" é *proxy* de recuperação — pode incluir cancelamento definitivo.
- A taxa de saída mensal oscila muito (23%–76%) e **não é previsível** pelas features
  da linha; só a *ordenação relativa* se mostrou estável.
- As faixas Alta/Média/Baixa são **tercis** da pontuação (prioridade relativa).
- A base tem apenas {met['n_rotulados']:,} linhas rotuladas em {len(analise['validacao'])} transições:
  as métricas são indicativas, não definitivas.
- A amostra é concentrada em uma região/UF, o que limita a generalização geográfica.

**Quer recalibrar?** Ao entrarem novos meses, o modelo se reajusta sozinho na próxima
execução (o cache é invalidado quando a base muda).
            """)

# ================= PAINEL 3: TOP CONTAS & CONCENTRAÇÃO =================
if ativo("contas"):
    st.markdown("### 🏢 Concentração de Risco B2B (Análise de Pareto)")
    
    # Ranking de clientes com curva ABC (agregação cacheada — Fase 2)
    client_agg = ad.clientes_agregados(df_filtered)
    
    col_pareto, col_top = st.columns([1.2, 1])
    
    with col_pareto:
        st.markdown("#### 📊 Curva de Pareto dos Maiores Clientes")
        fig_pareto = go.Figure()
        
        # Top 15 clientes para visualização
        top_15 = client_agg.head(15)
        
        fig_pareto.add_trace(go.Bar(
            x=top_15['CLIENTE'],
            y=top_15['TOTAL_LINHAS'],
            name='Linhas Suspensas',
            marker_color=tema.acento
        ))
        fig_pareto.add_trace(go.Scatter(
            x=top_15['CLIENTE'],
            y=top_15['PCT_ACUMULADO'],
            name='% Acumulado',
            yaxis='y2',
            line=dict(color=tema.alerta, width=3)
        ))
        fig_pareto.update_layout(
            template=template_plotly(tema),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(title='Quantidade de Linhas'),
            yaxis2=dict(title='% Acumulado', overlaying='y', side='right', range=[0, 105]),
            xaxis=dict(tickangle=-45),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=20, b=50)
        )
        _plot(fig_pareto, width='stretch')

    with col_top:
        st.markdown("#### 🏆 Top 10 Clientes com Maior Volume")
        fig_top_bar = px.bar(
            top_15.head(10).sort_values(by='TOTAL_LINHAS', ascending=True),
            x='TOTAL_LINHAS',
            y='CLIENTE',
            orientation='h',
            text='TOTAL_LINHAS',
            color='TEMPO_MEDIO_SUSPENSO',
            color_continuous_scale=list(tema.rampa),
            labels={'TOTAL_LINHAS': 'Qtd Linhas', 'TEMPO_MEDIO_SUSPENSO': 'Média Dias Suspenso'}
        )
        fig_top_bar.update_layout(
            template=template_plotly(tema),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=10, b=0)
        )
        _plot(fig_top_bar, width='stretch')

    # Drill-down detalhado por cliente (fragment — Fase 2)
    st.markdown("---")
    ficha_cliente(df_filtered, client_agg)

# ================= PAINEL 4: INTELIGÊNCIA GEOGRÁFICA =================
if ativo("geo"):
    st.markdown("### 🗺️ Inteligência Territorial & Distribuição Regional")
    st.markdown("""
    > **Destaque de Engenharia de Dados:** 100% dos registros foram recuperados e georreferenciados usando o DDD de origem telefônica.
    """)
    
    # Agregações geográficas cacheadas (Fase 2)
    uf_agg = ad.geo_por_uf(df_filtered)

    col_geo1, col_geo2 = st.columns([1.3, 1])
    
    with col_geo1:
        st.markdown("#### 📍 Ranking por Estado (UF)")
        
        fig_uf = px.bar(
            uf_agg,
            x='UF',
            y='TOTAL_LINHAS',
            text='TOTAL_LINHAS',
            color='TOTAL_LINHAS',
            color_continuous_scale=list(tema.rampa),
            labels={'TOTAL_LINHAS': 'Linhas Suspensas', 'UF': 'Estado'}
        )
        fig_uf.update_layout(
            template=template_plotly(tema),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=10, b=0)
        )
        _plot(fig_uf, width='stretch')

    with col_geo2:
        st.markdown("#### 📞 Distribuição por Código de Área (DDD)")
        ddd_agg = ad.geo_por_ddd(df_filtered, limite=12)
        
        fig_ddd = px.pie(
            ddd_agg,
            values='CONTAGEM',
            names='DDD',
            hole=0.45,
            color_discrete_sequence=list(tema.colorway)
        )
        fig_ddd.update_traces(textposition='inside', textinfo='percent+label')
        fig_ddd.update_layout(
            template=template_plotly(tema),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0)
        )
        _plot(fig_ddd, width='stretch')

    # Tabela Regional
    st.markdown("#### 📋 Detalhamento Territorial Consolidado")
    st.dataframe(uf_agg, width='stretch')

# ================= PAINEL 5: RÉGUA DE COBRANÇA & AÇÕES =================
if ativo("regua"):
    st.markdown("### ⚡ Régua de Acionamento & Cobrança Rápida")
    st.markdown("""
    > Acionamento ágil para a equipe de recuperação e retenção com mensagens padronizadas para o segmento corporativo.
    """)
    
    col_act1, col_act2 = st.columns([1.5, 1])
    
    with col_act1:
        # Gerador interativo como fragment (Fase 2 — UX)
        gerador_acionamento(df_filtered)
            
    with col_act2:
        st.markdown("#### 📥 Exportação de Dados")
        st.markdown("Exporte os dados filtrados para uso pelas equipes de telecobrança ou visitas em campo:")
        
        csv_export = df_filtered.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📄 Baixar Base Filtrada (CSV)",
            data=csv_export,
            file_name=f"parque_suspenso_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
        
        # 📕 Relatório Executivo em PDF (Página Única para Diretoria) — geração cacheada
        st.markdown("#### 📕 Relatório de Diretoria (PDF)")
        st.caption("Compila KPIs, MRR em risco, aging e Top clientes do recorte atual em 1 página.")
        try:
            dados_pdf = ad.pdf_do_recorte(df_filtered, ticket_medio, selected_ref, tema.nome)
            st.download_button(
                label="📕 Baixar Relatório Executivo (PDF)",
                data=dados_pdf,
                file_name=f"relatorio_parque_suspenso_{selected_ref.replace('/', '').replace(' ', '')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
            st.caption(f"💡 Ticket configurado: {fmt_brl(ticket_medio)}/linha → MRR em risco no recorte: {fmt_brl(df_filtered.shape[0] * ticket_medio)}")
        except Exception as pdf_err:
            log.exception("Falha ao gerar o relatório PDF: %s", pdf_err)
            st.warning(f"Não foi possível gerar o PDF. Instale o reportlab com `pip install reportlab`.\n\nDetalhe: {pdf_err}")
        
        st.markdown(f"""
        <div style="margin-top: 25px; padding: 15px; border-radius: 10px; background: {COR_BORDA}; border: 1px solid {COR_BORDA}; font-size: 12px; color: {COR_TEXTO_SEC};">
            <b>💡 Dica de Operação:</b><br>
            Clientes na faixa <i>Janela de Ouro (Até 30 dias)</i> apresentam taxa de reversão superior a 70% quando contatados nas primeiras 72 horas após a suspensão parcial.
        </div>
        """, unsafe_allow_html=True)

# ================= PAINEL 6: RASTREADOR DE RECUPERAÇÃO =================
if ativo("rastreador"):
    st.markdown("### 📞 Rastreador Nominal de Recuperação")
    st.markdown("""
    > Registro das ações de cobrança **por linha** (telefone + mês). Mede **SLA real de primeiro contato**,
    > taxa de conversão e produtividade por operador — fechando o ciclo entre a detecção do risco e a
    > recuperação efetiva.
    """)

    acoes = rt.carregar_acoes()
    kpis_rec = rt.resumo_acoes(acoes, df_base, ticket_medio)

    # Mensagem de confirmação do registro (flash: sobrevive ao st.rerun)
    flash = st.session_state.pop("_rec_flash", None)
    if flash:
        st.success(f"✅ {flash}")

    tempo_medio_1c = kpis_rec["tempo_medio_1o_contato"]
    aderencia = kpis_rec["pct_dentro_sla"]

    # ---------- KPIs do Rastreador ----------
    rc1, rc2, rc3, rc4, rc5 = st.columns(5)
    with rc1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Ações Registradas</div>
            <div class="metric-value" style="color: {COR_ACENTO};">{kpis_rec['total_acoes']:,}</div>
            <div class="metric-delta delta-neutral">{kpis_rec['linhas_acionadas']:,} linhas acionadas</div>
        </div>
        """, unsafe_allow_html=True)
    with rc2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Taxa de Conversão</div>
            <div class="metric-value" style="color: {COR_POSITIVO};">{kpis_rec['taxa_conversao']:.1f}%</div>
            <div class="metric-delta delta-neutral">{kpis_rec['linhas_recuperadas']:,} linhas recuperadas</div>
        </div>
        """, unsafe_allow_html=True)
    with rc3:
        valor_tempo = f"{tempo_medio_1c:.1f} <span style='font-size:16px;'>dias</span>" if tempo_medio_1c is not None else "—"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">1º Contato (médio)</div>
            <div class="metric-value" style="color: {COR_PERIGO};">{valor_tempo}</div>
            <div class="metric-delta delta-neutral">após a suspensão</div>
        </div>
        """, unsafe_allow_html=True)
    with rc4:
        valor_sla = f"{aderencia:.0f}%" if aderencia is not None else "—"
        cor_sla = tema.positivo if (aderencia or 0) >= 80 else tema.acento
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Aderência ao SLA</div>
            <div class="metric-value" style="color: {cor_sla};">{valor_sla}</div>
            <div class="metric-delta delta-neutral">alvo por faixa de risco</div>
        </div>
        """, unsafe_allow_html=True)
    with rc5:
        mrr_recuperado_ano = kpis_rec['mrr_recuperado'] * 12
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">MRR Recuperado</div>
            <div class="metric-value" style="color: {COR_POSITIVO};">{fmt_brl(kpis_rec['mrr_recuperado'])}</div>
            <div class="metric-delta delta-neutral">{fmt_brl(mrr_recuperado_ano)}/ano*</div>
        </div>
        """, unsafe_allow_html=True)

    if kpis_rec["total_acoes"] == 0:
        st.info(
            "ℹ️ **Nenhuma ação registrada ainda.** Use o formulário abaixo para começar a rastrear a "
            "recuperação — os indicadores e gráficos são preenchidos automaticamente a cada registro."
        )
    else:
        st.caption(
            f"* Projeção anual simples. Aderência calculada sobre {kpis_rec['com_data_suspensao']} "
            "linha(s) com data de suspensão conhecida."
        )

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

    # ---------- Registro + Análise por Canal/Resultado ----------
    col_reg, col_graf = st.columns([1.35, 1])

    with col_reg:
        registrar_acao_form(df_filtered, acoes)

    with col_graf:
        if not acoes.empty:
            st.markdown("#### 📊 Ações por Canal")
            canal_df = rt.acoes_por(acoes, "CANAL")
            fig_canal = px.bar(
                canal_df.sort_values("ACOES"), x="ACOES", y="CANAL", orientation="h",
                text="ACOES", color="ACOES", color_continuous_scale=list(tema.rampa),
            )
            fig_canal.update_traces(textposition="outside")
            fig_canal.update_layout(
                template=template_plotly(tema), paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)", showlegend=False, coloraxis_showscale=False,
                margin=dict(l=0, r=10, t=10, b=0), height=230,
            )
            _plot(fig_canal, width='stretch')

            st.markdown("#### 🎯 Resultado dos Contatos")
            res_df = rt.acoes_por(acoes, "RESULTADO")
            fig_res = px.pie(
                res_df, values="ACOES", names="RESULTADO", hole=0.5,
                color_discrete_sequence=list(tema.colorway),
            )
            fig_res.update_traces(textposition="inside", textinfo="percent+label")
            fig_res.update_layout(
                template=template_plotly(tema), paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False, margin=dict(l=0, r=0, t=10, b=0), height=250,
            )
            _plot(fig_res, width='stretch')
        else:
            st.markdown("#### 📊 Análise das Ações")
            st.caption("Os gráficos de canal e resultado aparecem após o primeiro registro.")

    # ---------- Evolução + SLA ----------
    if not acoes.empty:
        st.markdown("---")
        col_ev, col_sla = st.columns([1.2, 1])

        with col_ev:
            st.markdown("#### 📈 Evolução Semanal das Ações")
            sem = rt.acoes_por_semana(acoes)
            if not sem.empty:
                fig_ev = px.area(sem, x="SEMANA", y="ACOES", markers=True,
                                 color_discrete_sequence=[tema.acento])
                fig_ev.update_layout(
                    template=template_plotly(tema), paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=10, b=0), height=280,
                )
                _plot(fig_ev, width='stretch')

        with col_sla:
            st.markdown("#### ⏱️ SLA de Primeiro Contato por Faixa de Risco")
            tabela_sla = rt.sla_por_faixa(acoes, df_base)
            if tabela_sla.empty:
                st.caption("Sem linhas com data de suspensão conhecida para calcular o SLA.")
            else:
                st.dataframe(tabela_sla, width='stretch', hide_index=True)
                st.caption(
                    "SLA alvo: Janela de Ouro ≤ 3 dias · Atenção ≤ 2 dias · "
                    "Risco Crítico e Pré-Desconexão ≤ 1 dia."
                )

    # ---------- Recuperação observada (indicador indireto) ----------
    st.markdown("---")
    st.markdown("#### 🔄 Recuperação Observada (indicador indireto)")
    st.caption(
        "Linhas presentes em um mês e **ausentes no mês seguinte** — sinal objetivo de que a linha saiu "
        "do parque suspenso (reativação por pagamento ou cancelamento definitivo). Não depende do registro manual."
    )
    rec_obs = rt.recuperacao_observada(df_base)
    if rec_obs.empty:
        st.caption("São necessários ao menos dois meses na base para calcular este indicador.")
    else:
        col_tab, col_gr = st.columns([1, 1.3])
        with col_tab:
            st.dataframe(rec_obs, width='stretch', hide_index=True)
        with col_gr:
            fig_rec = px.bar(
                rec_obs, x="REFERENCIA_LABEL", y="TAXA_SAIDA_%", text="TAXA_SAIDA_%",
                color="TAXA_SAIDA_%", color_continuous_scale=list(tema.rampa),
                labels={"TAXA_SAIDA_%": "Taxa de saída (%)", "REFERENCIA_LABEL": "Mês"},
            )
            fig_rec.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_rec.update_layout(
                template=template_plotly(tema), paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)", showlegend=False, coloraxis_showscale=False,
                margin=dict(l=0, r=0, t=10, b=0), height=300,
            )
            _plot(fig_rec, width='stretch')

    # ---------- Histórico completo ----------
    if not acoes.empty:
        st.markdown("---")
        st.markdown("#### 🗂️ Histórico Completo de Ações")
        col_exp1, col_exp2 = st.columns([3, 1])
        with col_exp1:
            st.caption(f"{len(acoes)} ação(ões) registrada(s) — arquivo `acoes_recuperacao.csv`.")
        with col_exp2:
            st.download_button(
                label="📄 Baixar Histórico (CSV)",
                data=acoes.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig'),
                file_name=f"acoes_recuperacao_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width='stretch',
            )
        st.dataframe(
            rt.responder(acoes, df_base).sort_values("DT_ACAO", ascending=False),
            width='stretch', hide_index=True,
        )
