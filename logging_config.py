"""Configuração central de logging estruturado do projeto.

Uso:
    from logging_config import configurar_logging, get_logger
    log = configurar_logging("etl")     # console + arquivo rotativo
    log.info("mensagem")

Os logs são gravados em `logs/parque_suspenso.log` (rotação automática de 2 MB,
mantendo 3 backups). Nunca registre dados pessoais sensíveis: o helper
`mascarar()` está disponível para ofuscar telefones/CNPJ em mensagens de log.
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "parque_suspenso.log")

_FORMATO = "%(asctime)s | %(levelname)-8s | %(name)-14s | %(message)s"
_DATA_FMT = "%Y-%m-%d %H:%M:%S"

# Configuração padrão dos loggers do projeto (evita duplicação de handlers)
_LOGGERS_CONFIGURADOS = set()


def configurar_logging(nome: str = "parque_suspenso", nivel: int = logging.INFO,
                       arquivo: bool = True) -> logging.Logger:
    """Configura e devolve um logger do projeto (idempotente).

    Args:
        nome: nome do logger (ex.: "etl", "app", "relatorio").
        nivel: nível mínimo (padrão logging.INFO).
        arquivo: quando True, também grava em logs/parque_suspenso.log.
    """
    logger = logging.getLogger(nome)
    logger.setLevel(nivel)

    if nome in _LOGGERS_CONFIGURADOS:
        return logger

    formatter = logging.Formatter(_FORMATO, datefmt=_DATA_FMT)

    # Console (stdout) — tolerante a consoles sem suporte a UTF-8
    try:
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(formatter)
        logger.addHandler(stream)
    except Exception:
        pass

    # Arquivo rotativo
    if arquivo:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            handler = RotatingFileHandler(
                LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        except Exception as erro:
            logger.warning("Não foi possível iniciar o log em arquivo: %s", erro)

    logger.propagate = False
    _LOGGERS_CONFIGURADOS.add(nome)
    return logger


def get_logger(nome: str = "parque_suspenso") -> logging.Logger:
    """Devolve o logger já configurado (ou um logger simples, sem arquivo)."""
    if nome in _LOGGERS_CONFIGURADOS:
        return logging.getLogger(nome)
    return configurar_logging(nome)


def mascarar(valor: str, manter_inicio: int = 4, manter_fim: int = 2) -> str:
    """Ofusca identificadores sensíveis (telefone/CNPJ) para uso em logs."""
    texto = str(valor)
    if len(texto) <= manter_inicio + manter_fim:
        return "*" * len(texto)
    return f"{texto[:manter_inicio]}{'*' * (len(texto) - manter_inicio - manter_fim)}{texto[-manter_fim:]}"
