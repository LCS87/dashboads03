# 📡 Cockpit Executivo — Gestão de Parque Suspenso

Dashboard executivo em **Streamlit** para monitoramento, priorização e recuperação de **linhas corporativas suspensas** (parque suspenso B2B).

---

## 📊 Status Atual

| Indicador | Valor |
|---|---|
| Registros na base tratada | **2.061** (após deduplicação) |
| Meses cobertos | **5** — Jan a Mai/2026 |
| Clientes (CNPJ) monitorados | **821** |
| UFs identificadas | **15** (100% via DDD) |
| Painéis | **7** (Cockpit, Aging, Top Contas, Geografia, Régua, Rastreador, Todos) |
| Ações de recuperação registradas | arquivo `acoes_recuperacao.csv` (criado no 1º registro) |
| Modelo preditivo | AUC ≈ **0,57** (CV) · lift **1,58×** no tercil de maior prioridade |
| Colunas anonimizadas vazando | **0** |
| Testes automatizados | **131** testes pytest (≈15 s) |
| Validação da base | ✅ sem alertas fatais — 1 alerta de qualidade conhecido (Abr/2026) |

---

## 🚀 Início Rápido

### Opção 1 — 1 clique (Windows)

```bat
iniciar_dashboard.bat
```

O script verifica/instala dependências, detecta novos meses, executa o ETL se necessário e sobe o painel em **http://localhost:8503**.

### Opção 2 — manual

```bash
pip install -r requirements.txt
python etl_pipeline.py          # gera as bases tratadas
python -m streamlit run app.py --server.port 8503
```

### Opção 3 — Docker (recomendada para servidor)

```bash
docker compose up -d --build
# acesse http://localhost:8503
```

**Requisitos:** Python 3.11+ · Windows (o `.bat` é opcional — o projeto roda em qualquer SO) · Docker é opcional.

---

## 📁 Estrutura de Arquivos

### Código

| Arquivo | Função |
|---|---|
| `app.py` | Dashboard Streamlit (7 painéis, KPIs, filtros, exportações). |
| `etl_pipeline.py` | Pipeline de ETL: leitura, ingestão de novos meses, enriquecimento, deduplicação, validação e gravação. |
| `app_data.py` | Agregações **cacheadas** (`@st.cache_data`), regras de negócio e geração cacheada do PDF. |
| `rastreador.py` | **Rastreador Nominal de Recuperação**: persistência e métricas das ações de cobrança por linha (SLA, conversão, produtividade). |
| `modelo_risco.py` | **Modelo preditivo**: propensão de recuperação por linha (regressão logística em NumPy puro, validação cruzada e calibração). |
| `alertas.py` | **Motor de alertas e séries de tendência**: aplica 9 regras auditáveis sobre a base mensal e devolve sinais com nível, valor e a regra que os disparou. |
| `relatorio_pdf.py` | Relatório executivo em PDF (A4 paisagem, 1 página) via ReportLab. |
| `logging_config.py` | Logging estruturado (console + arquivo rotativo) e helper de mascaramento. |
| `iniciar_dashboard.bat` | Subida em 1 clique no Windows. |
| `requirements.txt` | Dependências de runtime. |
| `requirements-dev.txt` | Dependências de desenvolvimento (inclui `pytest`). |
| `tests/` | **Suíte pytest** (131 testes): ETL, agregações, alertas, modelo, rastreador e UI. |
| `pytest.ini` | Configuração do pytest (`testpaths`, marcador `ui`, filtros de warning). |
| `Dockerfile` | Imagem multi-estádio (`base` → `runtime` → `test`). |
| `docker-compose.yml` | Orquestração local e perfil de testes. |
| `docker/entrypoint.sh` | Bootstrap do contêiner: garante a base tratada e sobe o app. |
| `.dockerignore` | Exclui testes, docs e artefatos do contexto de build. |
| `.gitignore` | Proteção de segredos, caches e artefatos gerados. |

### Dados

| Arquivo | Papel |
|---|---|
| `parquesuspenso-janeiro a maio.csv` | **Base consolidada de origem** (`;`, latin1). Entrada principal do ETL. |
| `ParqueSuspenso_<mês>.csv` | Bases mensais individuais — usadas para **ingestão automática de novos meses** e para as mensagens de exemplo (Janeiro). |
| `parque_suspenso_tratado.parquet` | **Base tratada** (formato otimizado, consumida pelo dashboard). Gerada pelo ETL. |
| `parque_suspenso_tratado.csv` | Base tratada legível (fallback do dashboard e uso humano). Gerada pelo ETL. |
| `acoes_recuperacao.csv` | **Histórico de ações de recuperação** (append-only, delimitado por `;`). Criado/atualizado pelo painel Rastreador. |
| `logs/parque_suspenso.log` | Log rotativo (2 MB × 3 backups). Gerado em tempo de execução. |

### Documentação e configuração

| Arquivo | Conteúdo |
|---|---|
| `README.md` | Documentação central: status, uso, arquitetura, painéis e troubleshooting. |
| `CONTRIBUTING.md` | Guia de contribuição: ambiente, padrões de código, testes e regras invioláveis. |
| `CHANGELOG.md` | Histórico de mudanças por rodada (Keep a Changelog). |
| `PLANO_DE_ACAO_E_STATUS.md` | Plano de ação, entregas por rodada e **backlog**. |
| `ANALISE_E_PLANO_DE_MELHORIAS.md` | Análise técnica, plano de melhorias por fases e status de implementação. |
| `.streamlit/config.toml` | Tema dark corporativo e configuração do servidor. |

---

## 🏗️ Arquitetura e Fluxo de Dados

```
Bases mensais / consolidada (CSV)
    │
    ▼
 ┌────────────────────────────┐
 │      etl_pipeline.py       │
 │  1. Leitura robusta        │  encoding com fallback (utf-8-sig → latin1 → cp1252)
 │  2. Ingestão automática    │  detecta ParqueSuspenso_<mês>.csv ainda não consolidados
 │  3. Deduplicação           │  remove linhas 100% idêntidas (flag `REMOVER_DUPLICATAS_EXATAS`)
 │  4. Enriquecimento         │  DDD→UF, região, aging limpo, faixa de risco, CNPJ, datas
 │  5. Validação              │  colunas obrigatórias, REFERENCIA, datas, telefone, CNPJ
 │  6. Anonimização           │  descarta identificadores corporativos (DEALEAR, CD_DEALER, NOME_DIRETOR, NOME_DIVISAO)
 └────────────┬───────────────┘
              ▼
       parque_suspenso_tratado.parquet / .csv
              │
              ▼
 ┌────────────────────────────┐
 │         app.py           │  ← app_data.py (agregações cacheadas)
 │  7 painéis + KPIs + PDF  │  ← relatorio_pdf.py
 └────────────────────────────┘
```

**Separação de responsabilidades:** o dashboard **não** transforma dados — apenas consome a base tratada. Toda regra de negócio vive no ETL e em `app_data.py`.

---

## Etapas do ETL

| # | Etapa | Descrição |
|---|---|---|
| 0 | Ingestão automática | Anexa meses ainda não consolidados a partir de `ParqueSuspenso_*.csv`. |
| 0b | Deduplicação | Remove registros 100% idêntidos e registra o volume removido por mês. |
| 1 | Telefone | Normaliza para string de dígitos e extrai o **DDD**. |
| 2 | UF | Recupera UF ausente a partir do DDD (tabela oficial embutida). |
| 3 | Região | Agrupa UF em região geográfica. |
| 4 | Aging | Padroniza faixas e cria ordem de classificação. |
| 5 | Risco de churn | Converte aging em faixa de risco. |
| 6 | Referência | Gera rótulo legível do mês (`202606` → `Jun/2026`) dinamicamente. |
| 7 | Datas | Conversão e normalização de `DTPRIMEIRAATIVACAO` e `DT_SUSPENSAO`. |
| 8 | CNPJ | Formatação para exibição. |
| 9 | Mensagens | Integra mensagens de exemplo da base de Janeiro. |
| 10 | Anonimização | Descarte definitivo dos identificadores corporativos. |
| 11 | Validação final | Confere colunas obrigatórias + derivadas antes de gravar. |

---

## 📐 Regras de Negócio

### Faixas de Aging

`Até 30 dias` · `De 31 a 60 dias` · `De 61 a 90 dias` · `De 91 a 120 dias` · `Maior que 120 dias` · `Não Informado`

### Faixas de Risco de Churn

| Aging | Faixa de risco | Leitura de negócio |
|---|---|---|
| Até 30 dias | 🟢 **Baixo (Janela de Ouro)** | Alta recuperabilidade |
| 31 a 60 dias | 🟡 **Médio (Atenção)** | Risco moderado |
| 61 a 90 dias | 🔴 **Alto (Risco Crítico)** | Última janela de quitação |
| > 90 dias | 🟣 **Extremo (Pré-Desconexão)** | Cancelamento iminente |

> Linhas acima de **60–90 dias** entram na zona irreversível de cancelamento definitivo (churn involuntário).

### Parâmetros Executivos (sidebar)

| Parâmetro | Padrão | Faixa |
|---|---|---|
| Ticket Médio Mensal por Linha | **R$ 45,00** | R$ 10 – R$ 300 |
| Meta 0–30 dias (Janela de Ouro) | **60%** | 0–100% |
| Meta 31–60 dias (Atenção) | **40%** | 0–100% |

### MRR em Risco

```
MRR em risco = nº de linhas suspensas × ticket médio
```

Exibido no Cockpit (com projeção anual) e detalhado por faixa de aging no painel de Risco.

---

## 🖥️ Painéis do Dashboard

A navegação usa um seletor no topo: **apenas o painel ativo é renderizado** (lazy loading). A opção **🗂️ Todos os Painéis** mostra tudo de uma vez.

| Painel | Conteúdo |
|---|---|
| 📊 **Cockpit Executivo** | KPIs (linhas, clientes, % inadimplência, % risco crítico, tempo médio, **MRR em risco**), evolução histórica por status, donut de aging, distribuição por material e tipo de suspensão, **🚨 Central de Alertas**, **📈 Tendências e Variação Mensal** e a evolução da composição de aging por mês. |
| ⏳ **Aging & Risco de Churn** | Cartões por faixa de risco, **MRR em risco por faixa**, matriz de aging, painel de **metas/SLA** de recuperação e **🤖 propensão de recuperação (modelo preditivo)** com fila priorizada. |
| 🏢 **Top Contas & Concentração** | Análise de Pareto (curva ABC), Top clientes e **drill-down** por cliente. |
| 🗺️ **Inteligência Geográfica** | Ranking por UF, distribuição por DDD e detalhamento territorial. |
| ⚡ **Régua de Cobrança & Ações** | **Gerador de acionamento WhatsApp**, exportação CSV da base filtrada e **relatório PDF de diretoria**. |
| 📞 **Rastreador de Recuperação** | Registro nominal das ações por linha (telefone + mês), **SLA real de 1º contato**, taxa de conversão, MRR recuperado, produtividade por canal/operador e **recuperação observada** entre meses. |
| 🗂️ **Todos os Painéis** | Vista consolidada de todos os painéis simultâneos. |

---

## 📦 Filtros Globais (sidebar)

Mês de referência · UF · Faixa de aging · Status · Tipo de material · Busca livre (cliente, CNPJ ou telefone).

---

## 📞 Rastreador Nominal de Recuperação

Fecha o ciclo de negócio entre **detecção do risco** e **recuperação efetiva**: cada contato feito a uma linha suspensa é registrado e vira indicador de gestão.

### Como usar

1. Selecione o **painel 📞 Rastreador de Recuperação**.
2. No formulário **➕ Registrar Ação de Recuperação**, escolha o **cliente → linha** (telefone · mês · faixa de risco), o **canal**, o **resultado**, o **operador** e (opcionalmente) o **próximo retorno** e uma observação.
3. Clique em **💾 Registrar ação**. O registro é gravado em `acoes_recuperacao.csv` e os indicadores são recalculados na hora.

### O que é medido

| Indicador | Definição |
|---|---|
| **Ações registradas** | Total de contatos no histórico. |
| **Taxa de conversão** | Linhas com resultado `Recuperado` ÷ linhas acionadas. |
| **1º contato (médio)** | Dias entre `DT_SUSPENSAO` (da base) e a primeira ação registrada para a linha. |
| **Aderência ao SLA** | % de linhas cujo 1º contato ocorreu dentro do SLA da faixa de risco. |
| **MRR recuperado** | Linhas recuperadas × ticket médio (+ projeção anual). |
| **Recuperação observada** | Indicador *indireto*: linhas presentes em um mês e ausentes no mês seguinte (reativação por pagamento ou cancelamento). Não depende de registro manual. |

### SLA de primeiro contato (por faixa de risco)

| Faixa de risco | SLA alvo |
|---|:---:|
| Baixo (Janela de Ouro) | ≤ 3 dias |
| Médio (Atenção) | ≤ 2 dias |
| Alto (Risco Crítico) | ≤ 1 dia |
| Extremo (Pré-Desconexão) | ≤ 1 dia |

### Domínio registrável

- **Canais:** WhatsApp · Ligação · E-mail · SMS · Visita presencial · Outro.
- **Resultados:** Sem resposta · Contato efetivo · Promessa de pagamento · **Recuperado** · Recusou / não paga · Número inválido.

### Estrutura de `acoes_recuperacao.csv`

```
ID_ACAO;DT_ACAO;NUMTELEFONE;REFERENCIA;CLIENTE;CANAL;RESULTADO;OPERADOR;DT_RETORNO;OBSERVACAO
A00001;2026-05-04 09:12:00;81985874568;202605;29.704.572 CINTIA...;WhatsApp;Contato efetivo;Ana Souza;;cliente pediu boleto
```

- **Append-only:** o histórico nunca é sobrescrito; cada ação é uma linha.
- `ID_ACAO` sequencial (`A00001`), `REFERENCIA` no formato `AAAAmm` e `DT_RETORNO` opcional.
- Leitura tolerante: arquivo ausente ou parcial → o painel inicia vazio e se preenche a cada registro.
- O painel oferece **download do histórico completo** em CSV.

> **Privacidade:** o telefone é mascarado nas mensagens de log (`mascarar()`); o histórico local guarda o número completo por ser a chave operacional da linha.

---

## 🤖 Análise Preditiva — Propensão de Recuperação

Seção **🤖 Propensão de Recuperação** dentro do painel *Aging & Risco de Churn* (`modelo_risco.py`).

**Pergunta que responde:** *quais linhas suspensas têm maior chance de resolver no próximo mês — e portanto devem ser acionadas primeiro?* Transforma o aging (que olha só o passado) em uma **fila de trabalho priorizada**.

### Desenho

| Elemento | Definição |
|---|---|
| **Rótulo** | `SAIU` = 1 quando a linha existe no mês M e **não** existe em M+1; 0 quando continua suspensa. É o único sinal objetivo de reativação na base. |
| **Features** | `TEMPO_SUSPENSAO`, `DIAS_DESDE_ATIVACAO`, `MESES_CONSECUTIVOS`, `AGING_LIMPO`, `STATUS` — todas conhecidas **no** mês M. |
| **Modelo** | Regressão logística com regularização L2, implementada em **NumPy puro** (sem `scikit-learn`/`scipy`), convergindo por Newton-Raphson em < 10 iterações. |
| **Validação** | Cruzada *leave-one-month-out* (métrica principal) + holdout temporal (último mês) para a tabela de calibração. |
| **Calibração** | Intercepto reajustado por bisseção para que a probabilidade média iguale a taxa de saída do mês mais recente — corrige a superconfiança típica de amostras pequenas sem alterar a ordenação. |
| **Prioridade** | Tercis da própria pontuação (Alta / Média / Baixa) — prioridade **relativa**, não limiar absoluto. |

### Desempenho medido (base atual, 1.589 linhas rotuladas)

| Métrica | Valor |
|---|---|
| AUC em validação cruzada | **≈ 0,57** |
| AUC no holdout (Abr/2026) | **≈ 0,65** |
| Saída real no tercil de maior prioridade | **35,9%** (lift **1,58×**) |
| Saída real no tercil de menor prioridade | **11,8%** (lift 0,52×) |

**Leitura correta:** o modelo **ordena melhor que o acaso**, com poder discriminante **moderado**. Serve para priorizar a fila, **não** para afirmar probabilidades individuais.

### Transparência embutida na UI

O painel exibe, junto do resultado:

- **AUC (CV e holdout)** e os hiperparâmetros usados;
- **tabela de validação por mês** (deixar-um-mês-de-fora);
- **tabela de calibração por tercil** com o *lift* observado;
- **fatores que mais influenciam** (pesos padronizados, em gráfico);
- um bloco expansível **"Como o modelo funciona e quais são os limites"**.

> **Limites declarados:** "saiu do parque" é *proxy* de recuperação (pode incluir cancelamento definitivo); a taxa de saída mensal oscila entre ~23% e ~76% e **não é previsível** pelas features da linha — só a ordenação relativa se mostrou estável; a amostra é concentrada em uma região/UF.

### Reajuste automático

Ao entrarem novos meses, o modelo se retreina sozinho: o cache (`@st.cache_data`) é invalidado quando a base tratada muda.

---

## 🚨 Central de Alertas & Tendências

Seção dentro do painel *Cockpit Executivo* (`alertas.py`). Responde: *o que mudou no parque e merece atenção agora?* — em vez de o gestor ter de comparar meses mentalmente.

**Princípio:** todo alerta exibe **o número que o motivou** e **a regra em texto** (ex.: `volume do mês > média histórica × 1,5`). Nada de caixa preta — e cada regra é coberta por teste.

### Regras implementadas

| # | Alerta | Nível | Regra (parâmetro) |
|---|---|---|---|
| R1 | Pico de volume no mês | 🔴 Crítico | volume do mês **> média histórica × 1,5** (`FATOR_PICO`) |
| R2 | Queda de volume no mês | 🟢 Positivo | volume do mês **< média histórica × 0,8** (`FATOR_QUEDA`) |
| R3 | Alta consecutiva do parque | 🟠 Atenção | **3** variações mensais positivas seguidas (`MESES_ALTA_SEGUIDA`) |
| R4 | Criticidade alta no mês | 🔴 Crítico | aging crítico **> 35%** das linhas (`LIMITE_PCT_CRITICO`) |
| R4b | Criticidade sob controle | 🟢 Positivo | aging crítico **< 18%** |
| R5 | Concentração em poucos clientes | 🟠 Atenção | top 5 clientes **> 40%** das linhas do mês (`LIMITE_CONCENTRACAO`) |
| R6 | Telefones inválidos ou ausentes | 🟠 Atenção | telefones sem 10+ dígitos **> 5%** (`LIMITE_TELEFONE_INVALIDO`) |
| R7 | Duplicatas na base tratada | 🔴 Crítico | duplicatas exatas **> 0** |
| R8 | Base com um único mês | 🔵 Info | menos de **3** meses na base (`MIN_MESES_TENDENCIA`) |
| R9 | Aging de um mês fora do período | 🟠 Atenção | data de extração do bloco **> 45 dias** do 1º dia do mês (`TOLERANCIA_EXTRACAO_DIAS`) |

Os limites são **constantes explícitas no topo de `alertas.py`** — para calibrar, mude o número e rode a suíte (as regras têm teste de disparo e de não-disparo).

### Tendências e variação mensal

A tabela de tendência mostra, mês a mês, o volume de linhas, a **variação MoM** (`VAR_MOM_%`), o nº de clientes, o % crítico e o MRR em risco, além do gráfico de barras com a **média móvel de 3 meses** (`MM3`) — que suaviza oscilações pontuais.

> **Recorte real (Jan→Mai/2026):** 348 → 363 → 369 → **509** → 472 linhas. O "pico" de Abril era **artefato de carga duplicada** (corrigido no ETL) e, residualmente, **inconsistência de extração** (ver *Qualidade de Dados*) — o R9 sinaliza exatamente isso.

### ⚠️ Achado aberto: aging de Abr/2026 calculado fora do período

A coluna `TEMPO_SUSPENSAO` da origem é o número de dias entre `DT_SUSPENSAO` e a data em que o mês foi extraído — logo `DT_SUSPENSAO + TEMPO_SUSPENSAO` é **constante dentro de cada mês** e revela essa data com exatidão:

| Mês | Data de extração reconstruída | Desvio do 1º dia do mês |
|---|---:|:--:|
| Jan/2026 | 13/01/2026 | +12 ✅ |
| Fev/2026 | 06/02/2026 | +5 ✅ |
| Mar/2026 | 04/03/2026 | +3 ✅ |
| **Abr/2026** | **22/06/2026** | **+82 ❌** |
| Mai/2026 | 11/05/2026 | +10 ✅ |

**Consequência:** Abril aparece com **~92% de aging crítico** (contra ~4% a ~15% nos demais meses). Isso **não é um evento de negócio** — é inconsistência de extração. Como o aging alimenta a faixa de risco, a criticidade e o MRR em risco, **esses indicadores de Abril não são comparáveis** com os demais meses.

**O que o projeto já faz:**

1. **Detecta e alerta** — `extracoes_por_mes()` (`etl_pipeline.py`) reconstrói a data de extração por bloco, `validar_base()` emite alerta e o **R9** mostra o cartão na Central de Alertas.
2. **Documenta na UI** — o painel Cockpit tem o expander *"Evolução da composição de aging por mês (e o achado de Abr/2026)"*.
3. **Oferece correção opt-in** — `NORMALIZAR_AGING_POR_REFERENCIA = True` recalcula `TEMPO_SUSPENSAO`/`AGING` a partir de `DT_SUSPENSAO` (o campo confiável) e do mês de referência, tornando todos os meses comparáveis ("dias suspenso no 1º dia do mês").

> **Por que a correção vem desligada por padrão:** normalizar **muda um indicador de negócio** e existe uma segunda leitura possível (o bloco de Abril refletir uma extração posterior). A idade da suspensão por mês (`mês de referência − DT_SUSPENSAO`) é coerente em todos os meses — o que sustenta que os **rótulos** estão certos e o problema é só a coluna de tempo. Mesmo assim, a decisão é da área de negócio: por isso há alerta, documentação e flag, e não uma alteração silenciosa. Detalhes em `ANALISE_E_PLANO_DE_MELHORIAS.md`.

---

## 🧹 Qualidade de Dados

O ETL **remove automaticamente registros 100% idênticos** (flag `REMOVER_DUPLICATAS_EXATAS` em `etl_pipeline.py`) e registra o volume removido por mês no log. Nenhuma informação de negócio é perdida — apenas linhas totalmente iguais.

### ⚠️ Achado aberto: aging de Abr/2026 calculado fora do período

Ver seção "Central de Alertas & Tendências" acima.

### Validação

A validação (`validar_base()`) audita a cada execução: colunas obrigatórias/derivadas, faixa de `REFERENCIA` (AAAAmm), telefones curtos/nulos, datas inválidas/futuras/antigas, CNPJ nulo, duplicatas e **consistência da data de extração de cada bloco mensal**.

---

## 🔒 Anonimização e Segurança

- As colunas `DEALEAR`, `CD_DEALER`, `NOME_DIRETOR` e `NOME_DIVISAO` são **descartadas na gravação** das bases tratadas.
- Não há credenciais nem arquivos `.env` no projeto; o `.gitignore` cobre segredos, `secrets.toml`, chaves, caches e artefatos.
- O helper `mascarar()` ofusca telefone/CNPJ em mensagens de log.

---

## 📝 Logs e Diagnóstico

Todos os módulos registram em `logs/parque_suspenso.log` (console + arquivo rotativo):

- início/fim de cada execução do ETL e volume processado;
- ingestão de novos meses e deduplicação (com detalhe por mês);
- alertas de qualidade e falhas de validação (com traceback apenas no log);
- render de painel no dashboard e geração de PDF.

Exemplo de leitura rápida:

```powershell
Get-Content logs\parque_suspenso.log -Tail 30 -Encoding UTF8
```

---

## 🛠️ Solução de Problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| "Não foi possível carregar os dados" | Base tratada ausente/corrompida | `python etl_pipeline.py` |
| Aviso "Base desatualizada" na sidebar | Parquet antigo com duplicatas | Reexecutar o ETL |
| "Erro ao ler arquivo" | Encoding do CSV | O ETL tenta utf-8-sig, latin1 e cp1252 automaticamente |
| PDF não gera | `reportlab` ausente | `pip install reportlab` |
| Novo mês não aparece | Nome do arquivo fora do padrão | Renomear para `ParqueSuspenso_<mês>.csv` |
| Porta 8503 ocupada | Outra instância ativa | Fechar a anterior ou trocar `--server.port` |
| `docker compose up` falha no build | Sem acesso à internet/proxy | O build precisa baixar `python:3.11-slim` e as dependências |
| Contêiner reinicia em loop | Falha no ETL dentro do entrypoint | `docker compose logs ParqueSuspenso` |
| Permissão negada ao gravar CSV | Bind mount com dono diferente | O compose mapeia corretamente em Docker Desktop/WSL2 (validado) |
| Rastreador "sem ações" | `acoes_recuperacao.csv` ainda não existe | Registrar a 1ª ação pelo formulário do painel |
| Erro ao registrar ação | Operador/canal/resultado inválido | O painel valida e explica o campo; operador é obrigatório |
| Linha não aparece no formulário | Recorte da sidebar sem essa linha | Trocar o mês de referência ou usar "Todos os Meses" |
| Alerta *"Aging de Abr/2026 fora do período"* | Bloco mensal teve o aging calculado em outro mês (ver *Qualidade de Dados*) | O painel alerta — decisão de negócio: reextrair na origem **ou** ligar `NORMALIZAR_AGING_POR_REFERENCIA` |
| Central de Alertas sem cartões | Nenhum limite das regras foi atingido | Comportamento esperado — os limites estão em `alertas.py` |

---

## ✅ Testes e Validação

### Suíte automatizada (pytest)

```bash
pip install -r requirements-dev.txt
python -m pytest            # 131 testes, ~15 s
python -m pytest -m "not ui"   # só os rápidos (sem AppTest)
```

| Arquivo | Cobertura |
|---|---|
| `tests/test_etl.py` | `validar_base()` (fatal e não-estrito), deduplicação idempotente, helpers de domínio, consistência da extração (`extracoes_por_mes`, `descrever_extracao`), normalização de aging, ausência de colunas anonimizadas na base tratada. |
| `tests/test_app_data.py` | KPIs, faixas de risco, MRR por faixa, ordenação canônica, histórico mensal, Pareto de clientes, geo UF/DDD, qualidade e geração de PDF. |
| `tests/test_rastreador.py` | Persistência append-only, IDs sequenciais, validação de campos, KPIs, SLA por faixa, séries por canal/operador/semana e recuperação observada. |
| `tests/test_modelo_risco.py` | AUC (casos-limite), tercis, ausência de vazamento de meses futuros, convergência, calibração de intercepto, métricas e calibração monotônica. |
| `tests/test_alertas.py` | Séries mensais (MoM, média móvel, MRR), disparo **e não-disparo** de cada regra de alerta, ordenação por severidade, resumo por nível e tolerância a base vazia. |
| `tests/test_app.py` | Smoke de UI com `AppTest`: carga inicial, os **7 painéis**, "Todos os Painéis", filtros globais e o formulário do Rastreador (erro e sucesso). |

Os testes são **herméticos**: as fixtures redirecionam a persistência do rastreador para diretórios temporários e fazem backup/restore de `acoes_recuperacao.csv`, sem tocar nos dados reais.

### Smoke test manual

```bash
python -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('app.py'); at.run(); print(len(at.exception))"
```

---

## 🗺️ Roadmap — O que Falta / Próximos Passos

| Status | Prioridade | Item |
|:---:|:---:|---|
| ✅ **Concluído** | Alta | **Estimativa de Impacto Financeiro** | Ticket médio configurável (R$ 45/linha padrão) com MRR em risco no Cockpit, projeção anual e quebra por faixa de aging. |
| ✅ **Concluído** | Alta | **Ingestão Automática de Próximos Meses** | Detecção automática de novos `ParqueSuspenso_*.csv`, reprocessamento do Parquet e atualização dinâmica de eixos/filtros. Validado com Jun/2026 simulado. |
| ✅ **Concluído** | Média | **Exportação de Relatório Executivo em PDF** | `relatorio_pdf.py` gera relatório A4 de página única (KPIs, MRR, aging, Top 10 clientes) direto pela aba de ações. |
| ✅ **Concluído** | Média | **Metas e SLAs de Recuperação** | Metas configuráveis na sidebar + painel de progresso comparando normalização MoM das faixas 0-30d e 31-60d. |
| ✅ **Concluído** | — | **Higienização da Anonimização** | Exclusão efetiva de `DEALEAR`, `CD_DEALER`, `NOME_DIRETOR` e `NOME_DIVISAO` na gravação das bases tratadas. |
| ✅ **Concluído** | Alta | **Validação, Logs e Tratamento de Erros (Fase 1)** | `validar_base()` no ETL, exceção `ETLValidationError`, logging estruturado (`logging_config.py`) e mensagens de erro claras no dashboard. |
| ✅ **Concluído** | Alta | **Performance e Lazy Loading (Fase 2)** | Agregações cacheadas em `app_data.py`, navegação por painéis (`st.pills`) renderizando só o ativo, fragments para interações e PDF cacheado. |
| ✅ **Concluído** | Alta | **Diagnóstico das Duplicatas de Abr/2026** | Confirmado: 1.010 linhas 100% idênticas (mês carregado 3× no arquivo de origem). Aviso + toggle de deduplicação opcional no dashboard (sem alterar a base). |
| ✅ **Concluído** | Alta | **Correção do Pico de Abril/2026** | Deduplicação automática no ETL (`REMOVER_DUPLICATAS_EXATAS`): base passou de 3.071 → **2.061 registros** (Abril 1.519 → 509 reais), com log do volume removido por mês. |
| ✅ **Alta** | **Deploy em Rede Local / Servidor** | Script `iniciar_dashboard.bat` com modo `service`; PowerShell `install-service.ps1` com suporte a NSSM nativo e fallback manual; serviço criado e configurado. |
| ✅ **Alta** | **CI/CD** | Workflow `.github/workflows/test.yml` criado; roda `python -m pytest -m "not ui"` e `python -m pytest`. Nota: requer `git init` no repositório para ficar totalmente funcional. |
| ✅ **Baixa** | **Reexportar base de origem limpa** | Gerada cópia `parquesuspenso-janeiro a maio LIMPO.csv` (2061 linhas). Original mantido (3071 linhas) em `parquesuspenso-janeiro a maio.csv.bak`. |
| 🔜 **Média** | **Decidir sobre o aging de Abr/2026** | O bloco teve o aging calculado em 22/06/2026 (+82 dias), inflando a criticidade para ~92%. Escolher entre **reextrair o bloco na origem** ou ligar `NORMALIZAR_AGING_POR_REFERENCIA`. Enquanto isso, o ETL alerta e o Cockpit documenta o achado. |
| 🔜 **Baixa** | **Deploy em Rede Local / Servidor** | Configurar o painel como serviço do Windows (NSSM/WinSW) ou contêiner Docker para acesso simultâneo de outros computadores da rede interna, sem rodar localmente. |
| 🔜 **Baixa** | **CI/CD** | Pipeline de integração contínua (`.github/workflows`) — depende de `git init`, ainda não autorizado no projeto. |
| ✅ **Concluído** | Média | **Rastreador Nominal de Recuperação** | `rastreador.py` + painel 📞: log de ações por linha (data, canal, resultado, operador), SLA real de 1º contato, conversão e recuperação observada. |
| ✅ **Baixa** | **Alerta Automático de Pico** | `alertas.py` (regra R1: volume > 1,5× a média histórica) + **Central de Alertas** no Cockpit, com 9 regras auditáveis. |
| ✅ **Concluído** | Baixa | **Suíte de Testes Automatizados** | `tests/` com **131 testes**, fixtures herméticas e cobertura de ETL, agregações, alertas, modelo, rastreador e UI. |
| ✅ **Concluído** | Baixa | **Containerização (Docker)** | Imagem multi-estágio, usuário não-root e healthcheck; validada com bind mount no Windows. |
| ✅ **Concluído** | Baixa | **Qualidade de Código e Documentação** | Type hints/docstrings, `CONTRIBUTING.md`, `CHANGELOG.md`. |
| ✅ **Concluído** | Média | **Análise Preditiva (ML)** | `modelo_risco.py` + seção 🤖 no painel Aging: AUC ≈ 0,57 (CV), lift 1,58× no tercil prioritário. |
| ✅ **Concluído** | Média | **Central de Alertas & Tendências** | `alertas.py` (9 regras auditáveis) + **🚨 Central de Alertas** + **📈 Tendências** no Cockpit, com 9 regras auditáveis. |

**Pendências abertas:**

1. **Decidir sobre o aging de Abr/2026** — reextração na origem × `NORMALIZAR_AGING_POR_REFERENCIA` (ver *Qualidade de Dados*).
2. Higiene opcional: reexportar `parquesuspenso-janeiro a maio.csv` sem as linhas duplicadas (o ETL já as neutraliza automaticamente).
3. CI/CD (requer `git init`) e deploy como serviço do Windows.

---

## 🎯 Roadmap Sugerido

### Q4 2026 (Curto Prazo)
- ✅ Correções de segurança (Fase 1)
- ✅ Validação de dados, logs e tratamento de erros (Fase 1)
- ✅ Otimizações de performance e cache (Fase 2)
- ✅ Sistema de rastreamento de ações (Fase 3)
- ✅ Análise preditiva (ML), alertas e tendências (Fase 3)
- ✅ Docker e suíte pytest (Fase 4)

### Q1 2027 (Médio Prazo)
- ✅ Análise preditiva com ML *(antecipado)*
- ✅ Sistema de alertas no dashboard *(antecipado)*
- 🔜 Notificação ativa (e-mail/Teams) consumindo `alertas.detectar_alertas()`
- 🔜 Deploy em rede local como serviço do Windows
- 🔜 CI/CD (após `git init`)
- 🔜 Reexportar base de origem limpa (já gerada em `parquesuspenso-janeiro a maio LIMPO.csv`)

### Q2 2027 (Longo Prazo)
- 📱 App mobile ou PWA
- 🔗 Integrações (CRM, ERP)
- 🤖 Automação de cobranças

---

## 📚 Documentação Relacionada

- `PLANO_DE_ACAO_E_STATUS.md` — plano de ação e status das entregas
- `ANALISE_E_PLANO_DE_MELHORIAS.md` — análise técnica e plano de melhorias por fases
- `CONTRIBUTING.md` — guia de contribuição
- `CHANGELOG.md` — histórico de mudanças