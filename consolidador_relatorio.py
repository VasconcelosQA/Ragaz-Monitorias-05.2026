"""
consolidador_relatorio.py
Consolida análises do Claude por área e gera JSON pronto para importar no Lovable.
"""

import json
from datetime import datetime
from collections import Counter


def consolidar_relatorio(analises: list, periodo: str = None) -> dict:
    """
    Recebe lista de análises (output do analyzer.py) e retorna JSON consolidado por área.

    Estrutura de cada análise esperada:
    {
        "call_id": "...",
        "area": "SUCESSO_CORRETOR | ATENDIMENTO | COMERCIAL_CADASTRO",
        "gestor": "Nome",
        "data": "2026-05-01",
        "duracao_segundos": 245,
        "resultado_json": { ... }  # output do Claude
    }
    """

    if not periodo:
        periodo = datetime.now().strftime("%Y-%m")

    areas = {
        "SUCESSO_CORRETOR": [],
        "ATENDIMENTO": [],
        "COMERCIAL_CADASTRO": []
    }

    # Separar análises por área
    for analise in analises:
        area = analise.get("area", "").upper()
        if area in areas:
            areas[area].append(analise)

    relatorio = {
        "meta": {
            "gerado_em": datetime.now().isoformat(),
            "periodo": periodo,
            "total_analises": len(analises),
            "areas_monitoradas": [a for a in areas if len(areas[a]) > 0]
        },
        "consolidado_geral": _calcular_consolidado_geral(analises),
        "areas": {}
    }

    # Processar cada área
    for area, lista in areas.items():
        if lista:
            relatorio["areas"][area] = _processar_area(area, lista)

    return relatorio


def _calcular_consolidado_geral(analises: list) -> dict:
    total = len(analises)
    if total == 0:
        return {}

    efetivos = sum(1 for a in analises
                   if a.get("resultado_json", {}).get("efetivo") == "SIM")
    parciais = sum(1 for a in analises
                   if a.get("resultado_json", {}).get("efetivo") == "PARCIAL")
    nao_efetivos = sum(1 for a in analises
                       if a.get("resultado_json", {}).get("efetivo") == "NAO")

    prioridades = Counter(
        a.get("resultado_json", {}).get("prioridade_coaching", "")
        for a in analises
    )

    return {
        "total_analisadas": total,
        "efetivas": efetivos,
        "parciais": parciais,
        "nao_efetivas": nao_efetivos,
        "taxa_efetividade_pct": round((efetivos / total) * 100, 1) if total else 0,
        "coaching_alta_prioridade": prioridades.get("ALTA", 0),
        "coaching_media_prioridade": prioridades.get("MEDIA", 0),
        "coaching_baixa_prioridade": prioridades.get("BAIXA", 0)
    }


def _processar_area(area: str, analises: list) -> dict:
    total = len(analises)

    # Agrupamento por agente
    por_agente = {}
    for a in analises:
        nome = a.get("gestor", "Desconhecido")
        if nome not in por_agente:
            por_agente[nome] = []
        por_agente[nome].append(a)

    agentes_processados = []
    for nome, lista_agente in por_agente.items():
        agentes_processados.append(_processar_agente(nome, lista_agente, area))

    # Ordenar por taxa de efetividade decrescente
    agentes_processados.sort(
        key=lambda x: x["taxa_efetividade_pct"], reverse=True
    )

    # Falhas comuns (pontos críticos mais frequentes)
    todos_pontos_criticos = []
    for a in analises:
        pontos = a.get("resultado_json", {}).get("pontos_criticos", [])
        todos_pontos_criticos.extend(pontos)

    falhas_counter = Counter(todos_pontos_criticos)
    falhas_comuns = [
        {"descricao": k, "frequencia": v}
        for k, v in falhas_counter.most_common(5)
    ]

    # Boas práticas mais frequentes
    todas_boas_praticas = []
    for a in analises:
        boas = a.get("resultado_json", {}).get("boas_praticas", [])
        todas_boas_praticas.extend(boas)

    boas_counter = Counter(todas_boas_praticas)
    boas_praticas_top = [
        {"descricao": k, "frequencia": v}
        for k, v in boas_counter.most_common(3)
    ]

    # Campos específicos por área
    campos_especificos = _campos_especificos_area(area, analises)

    return {
        "area": area,
        "total_analisadas": total,
        "consolidado": _calcular_consolidado_geral(analises),
        "ranking_agentes": agentes_processados,
        "falhas_comuns": falhas_comuns,
        "boas_praticas_replicar": boas_praticas_top,
        "especifico": campos_especificos
    }


def _processar_agente(nome: str, analises: list, area: str) -> dict:
    total = len(analises)
    efetivos = sum(1 for a in analises
                   if a.get("resultado_json", {}).get("efetivo") == "SIM")
    parciais = sum(1 for a in analises
                   if a.get("resultado_json", {}).get("efetivo") == "PARCIAL")

    alta_prioridade = sum(1 for a in analises
                          if a.get("resultado_json", {}).get("prioridade_coaching") == "ALTA")

    # Nota média (para Atendimento que tem nota_final)
    notas = [a.get("resultado_json", {}).get("nota_final")
             for a in analises
             if a.get("resultado_json", {}).get("nota_final") is not None]
    nota_media = round(sum(notas) / len(notas), 1) if notas else None

    agente_data = {
        "nome": nome,
        "total_analisadas": total,
        "efetivas": efetivos,
        "parciais": parciais,
        "nao_efetivas": total - efetivos - parciais,
        "taxa_efetividade_pct": round((efetivos / total) * 100, 1) if total else 0,
        "coaching_alta_prioridade": alta_prioridade
    }

    if nota_media is not None:
        agente_data["nota_media"] = nota_media

    return agente_data


def _campos_especificos_area(area: str, analises: list) -> dict:
    """Campos específicos por área para o Lovable."""

    if area == "SUCESSO_CORRETOR":
        tipos = Counter(
            a.get("resultado_json", {}).get("tipo_pendencia_detectado", "")
            for a in analises
        )
        impactos = Counter(
            a.get("resultado_json", {}).get("impacto_receita", {}).get("resultado", "")
            for a in analises
        )
        return {
            "tipos_pendencia": dict(tipos),
            "impacto_receita": {
                "positivo": impactos.get("POSITIVO", 0),
                "neutro": impactos.get("NEUTRO", 0),
                "negativo": impactos.get("NEGATIVO", 0)
            }
        }

    elif area == "ATENDIMENTO":
        # Frequência de cumprimento por critério
        criterios = [
            "pronto_atendimento_saudacao",
            "atencao_concentracao",
            "entrega_solucao_efetiva",
            "clareza_seguranca",
            "transferencia_contato",
            "tempo_espera_resposta",
            "vocabulario",
            "cordialidade_empatia"
        ]
        resumo_criterios = {}
        for criterio in criterios:
            cumpriu = sum(1 for a in analises
                         if a.get("resultado_json", {})
                         .get("criterios", {})
                         .get(criterio, {})
                         .get("status") == "CUMPRIU")
            total = len(analises)
            resumo_criterios[criterio] = {
                "cumpriu": cumpriu,
                "nao_cumpriu": total - cumpriu,
                "pct": round((cumpriu / total) * 100, 1) if total else 0
            }
        return {"criterios_frequencia": resumo_criterios}

    elif area == "COMERCIAL_CADASTRO":
        tipos_contato = Counter(
            a.get("resultado_json", {}).get("tipo_contato", "")
            for a in analises
        )
        resultados = Counter(
            a.get("resultado_json", {})
            .get("resultado_comercial", {})
            .get("status", "")
            for a in analises
        )
        return {
            "tipos_contato": dict(tipos_contato),
            "resultado_comercial": {
                "convertido": resultados.get("CONVERTIDO", 0),
                "em_andamento": resultados.get("EM_ANDAMENTO", 0),
                "nao_convertido": resultados.get("NAO_CONVERTIDO", 0)
            }
        }

    return {}


def salvar_relatorio(relatorio: dict, caminho: str = None) -> str:
    """Salva o relatório consolidado em JSON."""
    if not caminho:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho = f"data/reports/consolidado_{timestamp}.json"

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)

    return caminho


# ─── EXEMPLO DE USO ───────────────────────────────────────────────

if __name__ == "__main__":
    # Simula 3 análises para teste
    analises_teste = [
        {
            "call_id": "20260501120530_34321",
            "area": "SUCESSO_CORRETOR",
            "gestor": "Aline De Souza",
            "data": "2026-05-01",
            "duracao_segundos": 245,
            "resultado_json": {
                "efetivo": "SIM",
                "confianca": 0.9,
                "tipo_pendencia_detectado": "PENDENCIA_PROPOSTA",
                "tipo_pendencia_especifico": "Recusa Reavaliavel",
                "padrao_comercial": {"nivel": "ALTO", "descricao": "Conduziu bem"},
                "impacto_receita": {"resultado": "POSITIVO", "motivo": "Proposta retomada"},
                "boas_praticas": ["Explorou motivo da recusa", "Ofereceu desconto estratégico"],
                "pontos_criticos": ["Não marcou follow-up"],
                "conformidade": {"status": "OK", "observacao": "Processo correto"},
                "resumo": "Ligação efetiva com boa condução comercial",
                "prioridade_coaching": "BAIXA"
            }
        },
        {
            "call_id": "20260502093000_12345",
            "area": "ATENDIMENTO",
            "gestor": "Lhaine",
            "data": "2026-05-02",
            "duracao_segundos": 180,
            "resultado_json": {
                "nota_final": 85,
                "efetivo": "SIM",
                "criterios": {
                    "pronto_atendimento_saudacao": {"status": "CUMPRIU", "peso": 10, "evidencia": "Saudou corretamente"},
                    "atencao_concentracao": {"status": "CUMPRIU", "peso": 15, "evidencia": "Manteve foco"},
                    "entrega_solucao_efetiva": {"status": "CUMPRIU", "peso": 20, "evidencia": "Resolveu a demanda"},
                    "clareza_seguranca": {"status": "CUMPRIU", "peso": 15, "evidencia": "Explicou bem"},
                    "transferencia_contato": {"status": "NAO_CUMPRIU", "peso": 10, "evidencia": "Não informou ramal"},
                    "tempo_espera_resposta": {"status": "CUMPRIU", "peso": 10, "evidencia": "Respondeu rápido"},
                    "vocabulario": {"status": "CUMPRIU", "peso": 10, "evidencia": "Linguagem adequada"},
                    "cordialidade_empatia": {"status": "CUMPRIU", "peso": 10, "evidencia": "Empática e educada"}
                },
                "pontos_fortes": ["Clareza técnica", "Empatia"],
                "pontos_desenvolvimento": ["Informar ramal na transferência"],
                "resumo": "Bom atendimento com falha pontual em transferência",
                "prioridade_coaching": "BAIXA"
            }
        },
        {
            "call_id": "20260503110000_67890",
            "area": "COMERCIAL_CADASTRO",
            "gestor": "Natália",
            "data": "2026-05-03",
            "duracao_segundos": 320,
            "resultado_json": {
                "efetivo": "PARCIAL",
                "confianca": 0.7,
                "tipo_contato": "CADASTRO_NOVO",
                "abordagem_comercial": {
                    "abertura": "MEDIA",
                    "qualificacao_corretor": "SIM",
                    "oferta_clara": "SIM",
                    "tratamento_objecao": "PARCIAL",
                    "fechamento": "NAO"
                },
                "resultado_comercial": {
                    "status": "EM_ANDAMENTO",
                    "proximo_passo": "Corretor vai pensar e retornar"
                },
                "impacto_receita": {"resultado": "NEUTRO", "motivo": "Sem conversão ainda"},
                "boas_praticas": ["Qualificou bem o perfil do corretor"],
                "pontos_criticos": ["Não tratou objeção de comissão", "Não fechou compromisso claro"],
                "conformidade": {"status": "ALERTA", "observacao": "Faltou fechamento"},
                "resumo": "Contato promissor mas sem fechamento",
                "prioridade_coaching": "MEDIA"
            }
        }
    ]

    relatorio = consolidar_relatorio(analises_teste, periodo="2026-05")
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
