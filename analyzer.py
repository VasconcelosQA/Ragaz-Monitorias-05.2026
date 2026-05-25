"""
Análise de transcrições via Claude API.
Roteia para o prompt correto de cada área e rastreia custo por token.
"""

import re
import json
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, MAX_TOKENS_ANALISE
from prompts import get_prompt_by_area

client = Anthropic(api_key=ANTHROPIC_API_KEY)


def analisar_ligacao(transcricao, contexto, area):
    """
    Analisa uma transcrição com o prompt da área.

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

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS_ANALISE,
            messages=[{"role": "user", "content": prompt}]
        )

        texto      = response.content[0].text
        uso        = response.usage

        # Extrair JSON da resposta
        json_match = re.search(r'\{.*\}', texto, re.DOTALL)
        if not json_match:
            return {
                "sucesso": False,
                "erro": "Resposta sem JSON válido",
                "raw": texto,
                "tokens_input": uso.input_tokens,
                "tokens_output": uso.output_tokens
            }

        analise = json.loads(json_match.group())

        # Garantir nota_final no Atendimento (soma os pesos de CUMPRIU)
        if area == "ATENDIMENTO" and analise.get("nota_final", 0) == 0:
            analise["nota_final"] = _calcular_nota_atendimento(analise)

        return {
            "sucesso"       : True,
            "analise"       : analise,
            "tokens_input"  : uso.input_tokens,
            "tokens_output" : uso.output_tokens,
            "erro"          : None
        }

    except json.JSONDecodeError as e:
        return {"sucesso": False, "erro": f"JSON inválido: {e}", "tokens_input": 0, "tokens_output": 0}
    except Exception as e:
        return {"sucesso": False, "erro": str(e), "tokens_input": 0, "tokens_output": 0}


def _calcular_nota_atendimento(analise):
    """Soma os pesos dos critérios com CUMPRIU para garantir nota correta."""
    nota = 0
    for criterio in analise.get("criterios", {}).values():
        if criterio.get("status") == "CUMPRIU":
            nota += criterio.get("peso", 0)
    return nota
