"""
Configurações centrais do sistema de monitorias Ragaz.
Edite aqui agentes, supervisores e modelos.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Áreas e agentes ────────────────────────────────────────────────────────────

AREAS = {
    "SUCESSO_CORRETOR": {
        "nome": "Sucesso do Corretor",
        "supervisor": "Diego",
        "agentes": ["Ariel", "Aline", "Taynnã", "Ligiane", "Eduardo", "Tatiana"],
        "pasta": "sucesso_corretor"
    },
    "ATENDIMENTO": {
        "nome": "Atendimento",
        "supervisor": "Danielle Moura",
        "agentes": ["Deuzeni", "Lhaine", "Talita", "Jéssica"],
        "pasta": "atendimento"
    },
    "COMERCIAL_CADASTRO": {
        "nome": "Comercial Cadastro",
        "supervisor": "Rodrigo",
        "agentes": ["Natália", "Ariely", "Ana Lúcia"],
        "pasta": "comercial_cadastro"
    }
}

# ── Claude ─────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Haiku 4.5: mais barato e rápido — use para rodadas grandes
CLAUDE_MODEL         = "claude-haiku-4-5-20251001"
CLAUDE_MODEL_PREMIUM = "claude-haiku-4-5-20251001"  # Mesmo modelo (sem fallback premium)

MAX_TOKENS_ANALISE = 700

# Preços por token (USD) — atualizar se mudarem
PRECO_HAIKU_INPUT   = 0.80  / 1_000_000
PRECO_HAIKU_OUTPUT  = 4.00  / 1_000_000
PRECO_SONNET_INPUT  = 3.00  / 1_000_000
PRECO_SONNET_OUTPUT = 15.00 / 1_000_000

# ── Transcrição ────────────────────────────────────────────────────────────────

DURACAO_MINIMA_SEGUNDOS = 10   # ignorar áudios muito curtos
IDIOMA_TRANSCRICAO      = "pt-BR"

# ── Pastas ─────────────────────────────────────────────────────────────────────

BASE_DIR   = r"G:\Meu Drive\MONITORIAS RAGAZ 05.26"
DADOS_DIR  = os.path.join(BASE_DIR, "dados")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
