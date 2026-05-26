"""
Análise de transcrições via Claude API com retry automático e fallback.
Roteia para o prompt correto de cada área e rastreia custo por token.
"""

import re
import json
import time
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, MAX_TOKENS_ANALISE
from prompts import get_prompt_by_area

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Só Haiku (mais barato) - sem fallback para Sonnet
MODELOS = [CLAUDE_MODEL]
MAX_RETRIES = 3
BACKOFF_INICIAL = 2  # segundo


def analisar_ligacao(transcricao, contexto, area):
    """
    Analisa uma transcrição com retry automático e fallback de modelo.

    Retorna dict:
    {
        "sucesso": bool,
        "analise": dict,          # JSON da análise
        "tokens_input": int,
        "tokens_output": int,
        "erro": str ou None
    }
    """
    if not transcricao or not transcricao.strip():
        return {"sucesso": False, "erro": "Transcrição vazia", "tokens_input": 0, "tokens_output": 0}

    prompt = get_prompt_by_area(area, contexto, transcricao)

    # Tentar cada modelo com retries
    for modelo_idx, modelo in enumerate(MODELOS):
        for tentativa in range(MAX_RETRIES):
            try:
                response = client.messages.create(
                    model=modelo,
                    max_tokens=MAX_TOKENS_ANALISE,
                    messages=[{"role": "user", "content": prompt}]
                )

                texto = response.content[0].text
                uso = response.usage

                # Extrair JSON da resposta
                json_match = re.search(r'\{.*\}', texto, re.DOTALL)
                if not json_match:
                    continue  # Tenta próxima tentativa

                analise = json.loads(json_match.group())

                # Garantir nota_final no Atendimento
                if area == "ATENDIMENTO" and analise.get("nota_final", 0) == 0:
                    analise["nota_final"] = _calcular_nota_atendimento(analise)

                return {
                    "sucesso"       : True,
                    "analise"       : analise,
                    "tokens_input"  : uso.input_tokens,
                    "tokens_output" : uso.output_tokens,
                    "erro"          : None
                }

            except json.JSONDecodeError:
                continue  # Tenta próxima tentativa
            except Exception as e:
                erro_str = str(e)
                # Se é erro 404 ou rate limit, faz backoff
                if "404" in erro_str or "rate_limit" in erro_str:
                    backoff = BACKOFF_INICIAL * (2 ** tentativa)
                    time.sleep(backoff)
                    continue
                # Se falhou com este modelo, tenta o próximo
                break

    # Nenhum modelo funcionou
    return {
        "sucesso": False,
        "erro": "Todos os modelos falharam após retries",
        "tokens_input": 0,
        "tokens_output": 0
    }


def _calcular_nota_atendimento(analise):
    """Soma os pesos dos critérios com CUMPRIU para garantir nota correta."""
    nota = 0
    for criterio in analise.get("criterios", {}).values():
        if criterio.get("status") == "CUMPRIU":
            nota += criterio.get("peso", 0)
    return nota
