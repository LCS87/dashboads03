# 📋 Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não publicado]

### Corrigido — Porta 8503 ocupada e inicialização resiliente
- `iniciar_dashboard.bat` agora **detecta a porta ocupada**, identifica o PID que a
  segura, **encerra a instância anterior** e segue — o script de 1 clique não falha
  mais com *"Port 8503 is not available"*.
- Aguarda até 10 s a liberação do socket antes de desistir, com mensagem clara e
  orientação para usar outra porta.
- **Novo parâmetro de porta**: `iniciar_dashboard.bat 8600` sobe em outra porta;
  `iniciar_dashboard.bat service` mantém o modo de serviço do Windows.
- Corrigido o `echo [!]` do batch, que criava um par de expansão inválido na
  expansão atrasada e corrompia a saída; `timeout` foi trocado por `ping` (o
  `timeout` falha quando o *stdin* está redirecionado).

### Corrigido — Dependências e ambiente
- `requirements.txt` agora traz **limites superiores** (`streamlit<2`, `pandas<4`,
  `numpy<3`, `plotly<8`, `pyarrow<30`, `reportlab<6`) para evitar saltos de versão
  principal com mudanças incompatíveis. Versões testadas registradas no README.
- `requirements-dev.txt` passou a incluir **`markdown-it-py`**, usado pelos testes de
  regressão de renderização Markdown — sem ele, 5 testes eram **pulados** silenciosamente.
- Validado com o conjunto mais novo (Python 3.11 · streamlit 1.66 · **pandas 3.0.6** ·
  **numpy 2.4.6** · **plotly 7.1.0** · pyarrow 26 · reportlab 5.0.1): **173/173 testes
  passando** e dashboard renderizando corretamente.

### Adicionado — Tema Gótico Vitoriano e Tema Pergaminho (claro)
- **Novo módulo [`tema.py`](tema.py)**: fonte única de verdade das cores, dos temas, do
  CSS dinâmico e do template Plotly. Nenhuma cor está mais hard-coded no `app.py`.
- **Dois temas de exibição**, alternáveis **em tempo de execução** na sidebar
  (`🎨 Tema de exibição`), sem reiniciar o servidor:
  - 🌙 **Gótico Vitoriano (escuro)** — preto carvão, bordô escuro, vermelho sangue,
    dourado envelhecido, pergaminho, cinza ferrugem, carmesim, verde musgo;
  - ☀️ **Pergaminho (claro)** — papel envelhecido, tinta sepia, ouro escuro, sangue.
- **Rampas sequenciais vitorianas** substituem as escalas padrão do Plotly
  (`Blues`, `Teal`, `RdBu_r`, `Reds`, `Blugrn`, `Bluyl`), que introduciam azuis
  destoantes da identidade visual — a aba *Inteligência Geográfica* é o caso mais
  evidente.
- **Tipografia vitoriana**: títulos em `Playfair Display` (serifa), corpo em
  `Plus Jakarta Sans`.
- `relatorio_pdf.py` recebe o tema ativo e usa uma **paleta de papel** própria
  (sempre impressa em fundo claro, com contraste AA).
- `app_data.pdf_do_recorte()` e `gerar_pdf()` passaram a aceitar o tema.
- Capturas do README (`assets/img01..img10`) **regeneradas** com o novo tema.

### Corrigido — Auditoria de acessibilidade (WCAG 2.1)
A paleta original do briefing falhava em 12 pares de cor realmente usados. Medição
objetiva das razões de contraste e correções:

| Uso | Antes | Agora |
|---|---:|---:|
| Verde musgo como **texto** (`.delta-negative`) | 1,96:1 | **4,50:1** |
| Vermelho sangue como **texto** (faixa extrema) | 1,92:1 | **4,58:1** |
| Carmesim como **texto** (`.delta-positive`) | 3,85:1 | **4,51:1** |
| Verde musgo como **borda/barra** | 1,96:1 | **4,50:1** |
| Ouro no PDF sobre branco | 3,25:1 | **4,69:1** |
| Cinza ferrugem no PDF sobre branco | 4,00:1 | **4,55:1** |

A regra adotada preserva a **paleta da marca** para preenchimento/borda/acento e usa
**variantes de mesmo matiz e saturação** (apenas a luminosidade muda) quando a cor
vira texto sobre fundo escuro. Todos os contrastes passam a ser **verificados por
teste automatizado**.

### Corrigido — Botão do WhatsApp renderizava como texto
O cartão de acionamento da aba ⚡ Régua de Cobrança aparecia com a tag
`<a href="https://wa.me/...">` impressa na tela. Causa raiz: em Markdown, **indentação
≥ 4 espaços** vira bloco de código e **linha em branco** encerra o bloco HTML — o
cartão inteiro era interpretado como código. Correções:
- cartão emitido em **linha única**, sem indentação e sem linha em branco;
- botão trocado por **`st.link_button`** (componente nativo, imune ao parser de
  Markdown e herda o tema);
- teste de regressão que falha se qualquer `<a href` vazar para o markdown.

### Corrigido — Navegação com item ativo ilegível
O Streamlit usa `primaryColor` como **cor do texto** do `pill` selecionado. Com o
vermelho sangue sobre o gradiente vermelho, o item ativo ficava em **1,9:1**.
Corrigido com regra CSS sobre `[data-testid="stButtonGroup"] button[data-selected]`.

### Corrigido — Eixos e legendas dos gráficos com a cor padrão do Plotly
O Plotly faz *merge* do template com o template padrão, e o padrão prevalecia — os
rótulos dos eixos ficavam em `#E6EAF1` (claro), invisíveis sobre papel. As cores do
tema passam a ser aplicadas como **propriedades explícitas do layout**, que sempre
vencem o template.

### Corrigido — `.gitignore` não ignorava nada
Os padrões estavam escritos como `*.csv$` e `*.parquet$`. No `.gitignore` o cifrão é
literal, então o padrão casaria apenas arquivos terminados em `.csv$` — ou seja,
**nada era ignorado** e os CSVs foram versionados. Corrigido para `*.csv`, `*.csv.bak`,
`*.xlsx`, `*.xls`, `*.xlsm`, `*.ods`, `*.parquet`, `*.feather`, `*.dta`, `*.sav` e
`*.tsv`. Os **7 arquivos de dados** foram removidos do índice do Git (os arquivos
permanecem no disco) e o `.dockerignore` foi revisado.

### Adicionado — Sanitização de mensagens
O nome da empresa, o telefone de atendimento e nomes de diretores/gerentes ainda
apareciam nas mensagens de cobrança (herdados dos CSVs de origem). Nova função
`etl_pipeline.sanitizar_mensagem()` aplicada em **duas camadas**:
1. **no ETL**, para que a base tratada nunca contenha a identificação;
2. **na interface**, protegendo bases antigas já gravadas.

Substituições: nome da empresa → `Telecomunicação S/A`; telefone real →
`(00) 00000-0000`; nomes de pessoas → `Responsável Comercial`. O ETL verifica o
resultado e registra no log se algo escapa. Verificado: **0 ocorrências** de nome da
empresa, telefone real ou nome de pessoa nas 2.061 mensagens da base.

### Corrigido — README reescrito (Metodologia, Limitações e Cronograma)
- `README.md` reescrito e ampliado (12 KB → ~80 KB, 1.330 linhas), passando a ser a
  **documentação central completa** do projeto, com 17 seções e sumário navegável.
- **Seção 3 — Metodologia** (nova): fluxo metodológico ponta a ponta, 12 etapas do ETL,
  deduplicação, enriquecimento, auditoria da base, a técnica de *assinatura temporal*
  que detectou a extração de Abr/2026, anonimização, **definições formais** de cada
  indicador, metodologia completa do modelo preditivo (rótulo, features, Newton-Raphson,
  calibração, protocolo de validação e leitura correta das métricas), metodologia das
  9 regras de alerta e do Rastreador, reprodutibilidade e governança da mudança.
- **Seção 8 — Limitações** (nova): 40+ limitações catalogadas em 6 famílias (dados,
  metodologia, modelo, medição/negócio, operação/engenharia, segurança/privacidade),
  cada uma com impacto e controle de mitigação; inclui a seção **"O que este projeto
  não afirma"**, para evitar leitura equivocada em comitês, e um resumo por criticidade.
- **Seção 9 — Riscos e Mitigações** (nova): 10 riscos com probabilidade, impacto,
  mitigação e responsável.
- **Seção 11 — Cronograma** (nova): linha do tempo das 13 rodadas concluídas com
  evidência de aceite, diagrama de Gantt, roadmap por horizonte (Q4/2026 · Q1/2027 ·
  Q2/2027), cronograma datado das próximas 11 entregas (S0–S10) com área, dependência
  e critério de aceite, diagrama de *gates* de decisão e riscos de cronograma.
- **Seção 2 — Status Atual** reescrita com **todos os números verificados
  programaticamente** contra a base tratada: 2.061 linhas, 821 clientes (850 CNPJ),
  15 UFs, 131 testes, AUC 0,571 (CV) / 0,654 (holdout), lift 1,58×.
- **Correção de inconsistência**: o README anterior atribuía o número **821** a
  "clientes (CNPJ)"; os 821 são **razões sociais** — há **850 CNPJ distintos**. A
  distinção foi explicitada e propagada para os demais documentos do projeto.
- Novas seções: Visão Geral (problema, objetivos, escopo e glossário), Arquitetura
  (contrato entre módulos e decisões de projeto), Testes e Qualidade (inclui comando
  de verificação de dados reproduzível), Segurança e Privacidade.
- **10 capturas reais** do dashboard (`assets/img01..img10`) incorporadas aos painéis
  correspondentes, com legendas explicativas do que cada tela mostra.
- **Galeria de preview no topo do README** (tabela HTML com 6 telas principais em
  tamanho reduzido) e reorganização da Seção 7, que agora traz as 10 telas em tamanho
  real — as duas capturas que faltavam (`img02` — visão geral do cockpit com navegação
  e filtros; `img08` — ranking das linhas mais antigas e cartões de AUC do modelo)
  foram efetivamente adicionadas, chegando a **100% das capturas utilizadas**.
- Sumário com âncoras HTML explícitas (`sec-N`, `preview`), para navegação estável
  apesar dos emojis nos títulos.

### Adicionado — Central de Alertas & Tendências
- `alertas.py`: motor de **9 regras auditáveis** (pico de volume, queda, alta
  consecutiva, criticidade alta/sob controle, concentração em top-5 clientes,
  telefones inválidos, duplicatas, base com um único mês e **aging de um mês
  calculado fora do período**). Cada alerta carrega nível, título, valor, detalhe
  e **a regra em texto** — nada de caixa preta.
- `series_mensais()`: série mensal com volume, clientes, criticidade, tempo médio,
  MRR em risco, **variação MoM** e **média móvel de 3 meses**.
- Seções **🚨 Central de Alertas** e **📈 Tendências e Variação Mensal** no Cockpit
  Executivo, com cartões por nível de severidade e tabela + gráfico de tendência.
- `app_data.serie_mensal()` e `app_data.alertas_do_painel()`: wrappers cacheados.
- Expander **"Evolução da composição de aging por mês"** no Cockpit, expondo o
  achado de qualidade de dados de Abr/2026.
- `tests/test_alertas.py`: 20 testes cobrindo disparo **e não-disparo** de cada
  regra, ordenação por severidade e tolerância a base vazia.

### Adicionado — Consistência da extração por bloco mensal
- `etl_pipeline.extracoes_por_mes()`: reconstrói a **data de extração** de cada
  bloco (`DT_SUSPENSAO + TEMPO_SUSPENSAO` é constante dentro do mês) e calcula o
  desvio em relação ao 1º dia do mês de referência.
- `etl_pipeline.descrever_extracao()`: descrição textual tolerante a datas
  indeterminadas (corrige quebra com `REFERENCIA` inválida).
- `validar_base()` passa a emitir alerta de qualidade e a devolver `resumo["extracoes"]`
  quando algum bloco foi calculado fora do seu período.
- `etl_pipeline.normalizar_aging()` + flag `NORMALIZAR_AGING_POR_REFERENCIA`
  (**desligada por padrão**): recalcula `TEMPO_SUSPENSAO`/`AGING` a partir de
  `DT_SUSPENSAO` e do mês de referência, tornando os meses comparáveis.
- **Achado:** o bloco de **Abr/2026** teve o aging calculado em **22/06/2026**
  (+82 dias), inflando a criticidade do mês para ~92% (contra ~4–15% nos demais).
  Documentado no README e sinalizado na UI; correção depende de decisão de negócio.

### Adicionado — Documentação e qualidade de código
- `CONTRIBUTING.md`: guia de contribuição (ambiente, padrões, testes, regras invioláveis).
- `CHANGELOG.md`: este arquivo.
- Type hints de parâmetro e retorno em **100%** das funções públicas de
  `etl_pipeline.py`, `relatorio_pdf.py` e `rastreador.py`.
- Docstrings onde faltavam (`clean_aging`, `df_clean_columns`, `_executar_etl`,
  `classificar_risco`, `formatar_cnpj`, `_fmt_brl`, `_moda`, `load_data`).

### Adicionado — Docker
- `Dockerfile` **multi-estágio** (`base` → `runtime` → `test`), usuário não-root
  (uid 1000) e `HEALTHCHECK` no endpoint nativo `/_stcore/health`.
- `docker-compose.yml` com persistência por bind mount, restart automático,
  timezone e perfil `testes` (`docker compose run --rm testes`).
- `docker/entrypoint.sh`: garante a base tratada (ETL) e absorve meses novos
  antes de subir o serviço. Validado em Docker Desktop/WSL2 — escrita em bind
  mount do Windows funcionando como uid 1000.
- `.dockerignore` enxugando o contexto de build.

### Adicionado — Suíte de testes
- `tests/` com **173 testes pytest** (ETL, agregações, alertas, modelo, rastreador
  e UI), executando em ~15 s.
- `tests/conftest.py` com fixtures **herméticas** (base real somente-leitura,
  recorte sintético de fallback e persistência do rastreador em `tmp_path`).
- `pytest.ini` (testpaths, marcador `ui`, filtros de warning) e
  `requirements-dev.txt`.
- Cobertura de UI via `streamlit.testing.v1.AppTest`: 6 painéis, "Todos os
  Painéis", filtros globais e o formulário do rastreador (erro e sucesso).

### Adicionado — Rastreador Nominal de Recuperação
- Módulo `rastreador.py`: persistência **append-only** em `acoes_recuperacao.csv`
  (`;`, UTF-8 com BOM) e métricas de recuperação.
- Novo painel **📞 Rastreador de Recuperação**: KPIs (ações, conversão, 1º contato,
  aderência ao SLA, MRR recuperado), formulário de registro, gráficos por canal e
  resultado, evolução semanal, SLA por faixa de risco e **recuperação observada**
  entre meses (indicador indireto).
- SLA de primeiro contato por faixa: Janela de Ouro ≤ 3 dias · Atenção ≤ 2 dias ·
  Risco Crítico e Pré-Desconexão ≤ 1 dia.
- Validação de domínio (`AcaoInvalidaError`) com mensagens amigáveis na UI.
- Mensagem de confirmação (*flash*) que sobrevive ao `st.rerun`.
- Download do histórico completo em CSV.

### Alterado
- `README.md` reescrito e mantido como documentação central: status, início rápido
  (3 opções), estrutura, arquitetura, regras de negócio, painéis, ingestão,
  Docker, qualidade, anonimização, logs, testes, troubleshooting e roadmap.

---

## [Rodada 6] — Limpeza e documentação

### Adicionado
- `README.md` (documentação central, ~12 KB).
- `.gitignore` preventivo (segredos, caches, artefatos gerados).

### Removido
- `parquesuspenso-janeiro a maio.xlsx` (arquivo em branco, sem referência no código).
- `__pycache__/` e código morto: `REF_TO_LABEL`,
  `app_data.deduplicar_registros_exatos`, imports não utilizados.

---

## [Rodada 5] — Correção do pico de Abril

### Corrigido
- **Base consolidada trazia Abr/2026 carregado 3×** (1.010 linhas 100% idênticas),
  inflando artificialmente o pico de volume do mês.
- Correção aplicada **no ETL** (`REMOVER_DUPLICATAS_EXATAS = True` +
  `remover_duplicatas_exatas()`), registrando o volume removido por mês no log.
- Resultado: **3.071 → 2.061 registros**; Abril de 1.519 → **509 linhas reais**;
  evolução coerente (Jan 348 → Fev 363 → Mar 369 → Abr 509 → Mai 472).
- A anotação "Pico de Volume" deixou de ser exibida indevidamente
  (regra `máximo > média × 1,5`).

### Removido
- Toggle manual de deduplicação na UI (desnecessário após a correção no ETL),
  mantendo apenas um alerta defensivo para Parquets antigos.

---

## [Rodada 4] — Performance e UX (Fase 2)

### Adicionado
- Agregações cacheadas (`@st.cache_data`) em `app_data.py`: KPIs, faixas de risco,
  financeiro por faixa, clientes/Pareto, geo UF/DDD e PDF do recorte.
- Navegação por `st.pills` com **lazy loading real** (apenas o painel ativo é
  renderizado) e opção **🗂️ Todos os Painéis**.
- `@st.fragment` em `ficha_cliente()` e `gerador_acionamento()`.
- Spinner, toast e logging no fluxo de carregamento.

### Desempenho medido
- Carga inicial ≈ 2.490 ms; troca de painel 186–815 ms; revisita com cache 182 ms;
  fragment 145 ms.

---

## [Rodada 3] — Confiabilidade (Fase 1)

### Adicionado
- `validar_base()` com `COLUNAS_OBRIGATORIAS` / `COLUNAS_DERIVADAS` e
  `ETLValidationError`; wrapper `run_etl()` com `log.exception`.
- `logging_config.py`: console + `logs/parque_suspenso.log` (rotativo 2 MB × 3) e
  helper `mascarar()` para telefone/CNPJ.
- Validação estrutural no app com mensagem clara e **auto-recuperação** (executa o
  ETL quando a base tratada falta ou está incompleta).
- ETL **agnóstico de mês/ano** via coluna `REFERENCIA` (fallback: nome do arquivo).
- Ingestão automática de novos meses (`refresh_if_new_months`).
- `.mode()` seguro, escape de HTML e guarda de telefone inválido no acionamento
  via WhatsApp.

### Corrigido
- `.env` era falso positivo da análise anterior: não existe `.env`, segredo ou
  repositório git no projeto.
