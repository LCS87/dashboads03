# 📋 Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não publicado]

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
- `tests/` com **131 testes pytest** (ETL, agregações, alertas, modelo, rastreador
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
