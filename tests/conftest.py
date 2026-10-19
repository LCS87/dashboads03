"""Fixtures compartilhadas da suíte de testes.

Estratégia:
- A base tratada real (`parque_suspenso_tratado.parquet`) é usada como fixture
  somente-leitura quando existir; caso contrário, um recorte sintético mínimo é
  construído para que os testes de UI/agregação continuem funcionando.
- Nenhum teste escreve nos artefatos reais do projeto: a persistência do
  rastreador é redirecionada para `tmp_path`.
"""
from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

PARQUET = os.path.join(PROJ_DIR, "parque_suspenso_tratado.parquet")


@pytest.fixture(scope="session")
def projeto_dir() -> str:
    """Diretório raiz do projeto."""
    return PROJ_DIR


@pytest.fixture(scope="session")
def base_tratada() -> pd.DataFrame:
    """Base tratada real (somente leitura) ou recorte sintético equivalente."""
    if os.path.exists(PARQUET):
        return pd.read_parquet(PARQUET)
    return _base_sintetica()


def _base_sintetica() -> pd.DataFrame:
    """Recorte mínimo com o mesmo esquema da base real (fallback)."""
    registros = []
    for i in range(12):
        ref = 202601 + (i % 3)
        registros.append({
            "CODCLI": 4000000000 + i,
            "CNPJ_CLIENTE": 29000000000000 + i,
            "CLIENTE": f"29.704.57{i} CLIENTE TESTE {i}",
            "MATERIAL": "TERMINAL",
            "AGING": ["ATÉ 30 DIAS", "DE 31 A 60 DIAS", "MAIOR QUE 120 DIAS"][i % 3],
            "STATUS": "INADIMPLENTE",
            "UF": ["PE", "SP", "RJ"][i % 3],
            "NUMTELEFONE": 81980000000 + i,
            "DTPRIMEIRAATIVACAO": pd.Timestamp("2025-01-01"),
            "DT_SUSPENSAO": pd.Timestamp("2025-12-01") + pd.Timedelta(days=i),
            "QT_DIAS": 30 + i,
            "TEMPO_SUSPENSAO": 20 + i,
            "TP_SUSPENSAO": "SUSPENSAO PARCIAL",
            "REFERENCIA": ref,
            "NUMTELEFONE_STR": str(81980000000 + i),
            "DDD": "81",
            "UF_ORIGINAL": "PE",
            "REGIAO": "Nordeste",
            "AGING_LIMPO": ["Até 30 dias", "De 31 a 60 dias", "Maior que 120 dias"][i % 3],
            "AGING_ORDEM": (i % 3) + 1,
            "FAIXA_RISCO": ["Baixo (Janela de Ouro)", "Médio (Atenção)", "Extremo (Pré-Desconexão)"][i % 3],
            "REFERENCIA_LABEL": f"{ref % 100:02d}/{ref // 100}",
            "CNPJ_FORMATADO": "29.700.000/0000-00",
            "MSG_EXEMPLO": "mensagem de exemplo",
            "MSG_COBRANCA": "mensagem de cobrança",
        })
    return pd.DataFrame(registros)


@pytest.fixture()
def rastreador_tmp(tmp_path, monkeypatch):
    """Módulo `rastreador` com persistência redirecionada para arquivo temporário."""
    import rastreador as rt

    monkeypatch.setattr(rt, "ARQUIVO_ACOES", str(tmp_path / "acoes_recuperacao.csv"))
    return rt
