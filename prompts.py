"""
Prompts de análise por área.
Cada função retorna o prompt pronto para enviar ao Claude.
"""


# ── Sucesso do Corretor ────────────────────────────────────────────────────────

def get_prompt_sucesso_corretor(gestor, telefone, tipo_pendencia, duracao, transcricao):
    return f"""Você é um analista especializado em equipes comerciais de seguros.
Avalie essa ligação com foco em resultado e receita.

CONTEXTO:
- Gestor: {gestor}
- Tipo de pendência: {tipo_pendencia}
- Duração: {duracao}s
- Telefone: {telefone}

TRANSCRIÇÃO:
{transcricao}

Responda APENAS em JSON válido:
{{
  "efetivo": "SIM ou NAO ou PARCIAL",
  "confianca": 0.0,
  "tipo_pendencia_detectado": "PENDENCIA_PROPOSTA ou ATIVACAO ou ONBOARDING ou OUTRO",
  "tipo_pendencia_especifico": "Recusa Reavaliavel ou Rastreador ou Desconto ou Vistoria ou Outro",
  "padrao_comercial": {{
    "nivel": "ALTO ou MEDIO ou BAIXO",
    "descricao": "Como o gestor conduziu — uma frase objetiva"
  }},
  "spin_aplicado": {{
    "situacao": "SIM ou NAO ou PARCIAL",
    "problema": "SIM ou NAO ou PARCIAL",
    "implicacao": "SIM ou NAO ou PARCIAL",
    "necessidade": "SIM ou NAO ou PARCIAL"
  }},
  "impacto_receita": {{
    "resultado": "POSITIVO ou NEUTRO ou NEGATIVO",
    "motivo": "Por que essa ligação ajudou ou prejudicou a receita"
  }},
  "boas_praticas": ["O que foi feito bem e deve ser replicado"],
  "pontos_criticos": ["O que travou, faltou ou pode custar dinheiro"],
  "conformidade": {{
    "status": "OK ou ALERTA ou CRITICO",
    "observacao": "Processo seguido corretamente ou o que fugiu do padrão"
  }},
  "resumo": "Uma frase sobre o desempenho nessa ligação",
  "prioridade_coaching": "ALTA ou MEDIA ou BAIXA"
}}"""


# ── Atendimento ────────────────────────────────────────────────────────────────

def get_prompt_atendimento(agente, telefone, duracao, transcricao):
    return f"""Você é um especialista em qualidade de atendimento ao cliente em seguros.
Avalie essa ligação com base no modelo binário de 8 critérios da Ragaz.

CONTEXTO:
- Agente: {agente}
- Telefone: {telefone}
- Duração: {duracao}s

TRANSCRIÇÃO:
{transcricao}

Avalie cada critério como CUMPRIU ou NAO_CUMPRIU com base nas evidências da transcrição.
Calcule nota_final somando o peso de cada critério com status CUMPRIU.

Responda APENAS em JSON válido:
{{
  "nota_final": 0,
  "criterios": {{
    "pronto_atendimento_saudacao": {{
      "status": "CUMPRIU ou NAO_CUMPRIU",
      "peso": 10,
      "evidencia": "O que foi observado na transcrição"
    }},
    "atencao_concentracao": {{
      "status": "CUMPRIU ou NAO_CUMPRIU",
      "peso": 15,
      "evidencia": "O que foi observado"
    }},
    "entrega_solucao_efetiva": {{
      "status": "CUMPRIU ou NAO_CUMPRIU",
      "peso": 20,
      "evidencia": "O que foi observado"
    }},
    "clareza_seguranca": {{
      "status": "CUMPRIU ou NAO_CUMPRIU",
      "peso": 15,
      "evidencia": "O que foi observado"
    }},
    "transferencia_contato": {{
      "status": "CUMPRIU ou NAO_CUMPRIU",
      "peso": 10,
      "evidencia": "O que foi observado"
    }},
    "tempo_espera_resposta": {{
      "status": "CUMPRIU ou NAO_CUMPRIU",
      "peso": 10,
      "evidencia": "O que foi observado"
    }},
    "vocabulario": {{
      "status": "CUMPRIU ou NAO_CUMPRIU",
      "peso": 10,
      "evidencia": "O que foi observado"
    }},
    "cordialidade_empatia": {{
      "status": "CUMPRIU ou NAO_CUMPRIU",
      "peso": 10,
      "evidencia": "O que foi observado"
    }}
  }},
  "pontos_fortes": ["Item 1", "Item 2"],
  "pontos_desenvolvimento": ["Item 1", "Item 2"],
  "padrao_identificado": "Descrição de padrão recorrente se houver",
  "resumo": "Uma frase sobre o atendimento",
  "prioridade_coaching": "ALTA ou MEDIA ou BAIXA"
}}"""


# ── Comercial Cadastro ─────────────────────────────────────────────────────────

def get_prompt_comercial_cadastro(agente, telefone, duracao, transcricao):
    return f"""Você é um especialista em análise de performance comercial de seguros.
A área de Comercial Cadastro é a porta de entrada da Ragaz: responsável por cadastrar corretores novos, oferecer novas bandeiras e converter interesse em parceria ativa.
Avalie essa ligação com olhar de closer — não de atendimento.

CONTEXTO:
- Agente: {agente}
- Telefone: {telefone}
- Duração: {duracao}s

TRANSCRIÇÃO:
{transcricao}

Responda APENAS em JSON válido:
{{
  "efetivo": "SIM ou NAO ou PARCIAL",
  "confianca": 0.0,
  "tipo_contato": "CADASTRO_NOVO ou OFERTA_BANDEIRA ou REATIVACAO ou OUTRO",
  "abordagem_comercial": {{
    "abertura": "FORTE ou MEDIA ou FRACA",
    "qualificacao_corretor": "SIM ou NAO ou PARCIAL",
    "oferta_clara": "SIM ou NAO",
    "tratamento_objecao": "SIM ou NAO ou SEM_OBJECAO",
    "fechamento": "SIM ou NAO ou PARCIAL"
  }},
  "spin_aplicado": {{
    "situacao": "SIM ou NAO ou PARCIAL",
    "problema": "SIM ou NAO ou PARCIAL",
    "implicacao": "SIM ou NAO ou PARCIAL",
    "necessidade": "SIM ou NAO ou PARCIAL"
  }},
  "resultado_comercial": {{
    "status": "CONVERTIDO ou EM_ANDAMENTO ou NAO_CONVERTIDO",
    "proximo_passo": "Qual foi o combinado ou por que não houve"
  }},
  "impacto_receita": {{
    "resultado": "POSITIVO ou NEUTRO ou NEGATIVO",
    "motivo": "Por que essa ligação contribuiu ou não para resultado"
  }},
  "boas_praticas": ["O que funcionou e deve ser replicado"],
  "pontos_criticos": ["O que travou a conversão ou pode impactar resultado"],
  "conformidade": {{
    "status": "OK ou ALERTA ou CRITICO",
    "observacao": "Seguiu o processo ou o que fugiu do padrão"
  }},
  "resumo": "Uma frase sobre o desempenho comercial nessa ligação",
  "prioridade_coaching": "ALTA ou MEDIA ou BAIXA"
}}"""


# ── Roteador ───────────────────────────────────────────────────────────────────

def get_prompt_by_area(area, contexto, transcricao):
    if area == "SUCESSO_CORRETOR":
        return get_prompt_sucesso_corretor(
            contexto.get("gestor", "N/A"),
            contexto.get("telefone", "N/A"),
            contexto.get("tipo_pendencia", "N/A"),
            contexto.get("duracao", 0),
            transcricao
        )
    elif area == "ATENDIMENTO":
        return get_prompt_atendimento(
            contexto.get("gestor", "N/A"),
            contexto.get("telefone", "N/A"),
            contexto.get("duracao", 0),
            transcricao
        )
    elif area == "COMERCIAL_CADASTRO":
        return get_prompt_comercial_cadastro(
            contexto.get("gestor", "N/A"),
            contexto.get("telefone", "N/A"),
            contexto.get("duracao", 0),
            transcricao
        )
    else:
        raise ValueError(f"Área desconhecida: {area}")
