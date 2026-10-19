# 🤝 Guia de Contribuição

Obrigado pelo interesse em contribuir com o **Cockpit Executivo — Parque Suspenso**.
Este documento descreve o ambiente, os padrões de código e o fluxo de trabalho.

---

## 1. Preparando o ambiente

```bash
git clone <url-do-repositorio>      # ou copie a pasta do projeto
cd dashboads03

python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install -r requirements-dev.txt   # inclui requirements.txt + pytest
python etl_pipeline.py               # gera a base tratada
python -m streamlit run app.py --server.port 8503
```

Atalho no Windows: `iniciar_dashboard.bat`.
Alternativa containerizada: `docker compose up -d --build`.

**Requisitos:** Python 3.11+ (o projeto usa `X | None` em anotações e `match`-free moderno).

---

## 2. Antes de abrir um Pull Request

```bash
python -m py_compile app.py app_data.py etl_pipeline.py relatorio_pdf.py rastreador.py logging_config.py
python -m pytest                  # suíte completa (131 testes)
python -m pytest -m "not ui"      # apenas os testes rápidos
```

Nenhum PR é aceito com teste quebrado ou exceção na renderização de painel.

---

## 3. Padrões de código

| Aspecto | Regra |
|---|---|
| Idioma (UI e docs) | **Português** |
| Idioma (nomes de código) | Português para domínio (`faixa_risco`, `acoes_por_canal`); inglês tolerado em nomes consagrados (`load_data`, `cache_data`) |
| Formatação | 4 espaços, sem tabs; linhas até ~100 colunas |
| Tipagem | **Anotar** parâmetros e retorno em funções públicas (`-> dict`, `df: pd.DataFrame`) |
| Docstrings | Obrigatórias em funções públicas; formato com resumo na 1ª linha e `Args:`/`Returns:` quando útil |
| Caching | Toda agregação pesada deve usar `@st.cache_data` em `app_data.py` |
| Logging | Usar `get_logger(__name__)`; **nunca** `print` em código de produção |
| Dados sensíveis | Usar `mascarar()` em telefone/CNPJ antes de logar |

### Exemplo de função conforme o padrão

```python
@st.cache_data(show_spinner=False)
def geo_por_uf(df: pd.DataFrame) -> pd.DataFrame:
    """Volume e tempo médio por UF."""
    if df.empty:
        return pd.DataFrame(columns=["UF", "TOTAL_LINHAS", "TEMPO_MEDIO"])
    ...
```

---

## 4. Arquitetura — onde mexer

| Quero… | Mexa em |
|---|---|
| Adicionar KPI/gráfico a um painel existente | `app.py` (bloco `if ativo("<painel>"):`) |
| Criar um painel novo | `PAINEIS` em `app.py` + bloco no fim do arquivo + tabela do README |
| Criar uma agregação cacheada | `app_data.py` |
| Mudar regra de negócio (aging, faixa de risco, MRR) | `app_data.py` + `ANALISE_E_PLANO_DE_MELHORIAS.md` |
| Mudar leitura/enriquecimento/deduplicação | `etl_pipeline.py` |
| Mexer no log de recuperação | `rastreador.py` |
| Mudar o PDF | `relatorio_pdf.py` |

> **Nunca** coloque regra de negócio dentro de `app.py`: o dashboard deve apenas orquestrar.

---

## 5. Regras invioláveis

1. **Anonimização** — as colunas `DEALEAR`, `CD_DEALER`, `NOME_DIRETOR` e `NOME_DIVISAO`
   **não podem** ser gravadas nas bases tratadas nem exibidas na UI. O teste
   `test_base_tratada_sem_colunas_anonimizadas` cobre isso.
2. **Sem segredos no código** — credenciais vão para `.env` (já no `.gitignore`).
3. **Testes herméticos** — testes nunca escrevem em `acoes_recuperacao.csv`,
   `parque_suspenso_tratado.*` ou `logs/`. Use `tmp_path` / `monkeypatch`.
4. **Idempotência do ETL** — rodar o pipeline duas vezes deve produzir exatamente
   o mesmo resultado (mesmo número de linhas, zero duplicatas).
5. **Compatibilidade de meses** — nada de hardcode de mês/ano: use a coluna `REFERENCIA`.

---

## 6. Adicionando um teste

Os testes ficam em `tests/` e são divididos por módulo:

- `test_etl.py` — pipeline, validação, deduplicação e consistência da extração.
- `test_app_data.py` — agregações e regras de negócio.
- `test_alertas.py` — séries mensais e regras de alerta (disparo e não-disparo).
- `test_modelo_risco.py` — modelo preditivo, AUC e anti-vazamento.
- `test_rastreador.py` — persistência e métricas do rastreador.
- `test_app.py` — UI via `AppTest` (marcados com `@pytest.mark.ui`).

Use as fixtures de `tests/conftest.py`:

| Fixture | O que fornece |
|---|---|
| `projeto_dir` | Caminho absoluto da raiz do projeto. |
| `base_tratada` | Base real (somente leitura) ou recorte sintético equivalente. |
| `rastreador_tmp` | Módulo `rastreador` com persistência em arquivo temporário. |

---

## 7. Commits e Pull Requests

- Mensagens no imperativo, em português: `Adiciona cálculo de SLA por faixa de risco`.
- Um PR = uma mudança coerente. Evite misturar refatoração com feature.
- Descreva no PR: **o que** mudou, **por que** e **como validar** (comando + resultado).
- Se alterar comportamento visível, atualize o `README.md` e o `CHANGELOG.md`.

---

## 8. Documentação

| Documento | Quando atualizar |
|---|---|
| `README.md` | Sempre que mudar UI, comando, estrutura ou indicador. |
| `CHANGELOG.md` | Em toda mudança relevante para o usuário. |
| `PLANO_DE_ACAO_E_STATUS.md` | Ao concluir/abrir um item do backlog. |
| `ANALISE_E_PLANO_DE_MELHORIAS.md` | Ao concluir uma fase do plano técnico. |
