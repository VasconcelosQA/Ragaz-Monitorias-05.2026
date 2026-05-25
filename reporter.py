"""
Geração de relatórios JSON para o Lovable e Excel consolidado.
"""

import json
from datetime import datetime
from collections import Counter, defaultdict
from config import AREAS, PRECO_HAIKU_INPUT, PRECO_HAIKU_OUTPUT


# ── Por área ───────────────────────────────────────────────────────────────────

def gerar_relatorio_area(area_key, resultados, periodo, custo_usd=0.0):
    """
    Gera o JSON completo de uma área, pronto para importar no Lovable.

    resultados = lista de dicts retornados pelo main após processar cada áudio,
    já incluindo: ligacao_id, agente, duracao, data, sucesso, analise
    """
    cfg       = AREAS[area_key]
    analisadas = [r for r in resultados if r.get("sucesso")]

    consolidado = _consolidado_area(area_key, resultados, analisadas, custo_usd)
    gestores    = _gestores_area(area_key, analisadas)
    falhas      = _top_itens(_coletar_campo(analisadas, area_key, "pontos_criticos"), 6)
    praticas    = _top_itens(_coletar_campo(analisadas, area_key, "boas_praticas"),   6)

    return {
        "periodo"                 : periodo,
        "gerado_em"               : datetime.now().isoformat(),
        "area"                    : cfg["nome"],
        "area_key"                : area_key,
        "supervisor"              : cfg["supervisor"],
        "consolidado"             : consolidado,
        "ranking_gestores"        : gestores,
        "falhas_comuns"           : falhas,
        "boas_praticas_replicaveis": praticas,
        "ligacoes"                : [_resumo_ligacao(r, area_key) for r in analisadas]
    }


def _consolidado_area(area_key, todos, analisadas, custo_usd):
    base = {
        "total_ligacoes"  : len(todos),
        "analisadas"      : len(analisadas),
        "cobertura_pct"   : _pct(len(analisadas), len(todos)),
        "custo_analise_usd": round(custo_usd, 4)
    }

    if area_key == "SUCESSO_CORRETOR":
        efetivas = [r for r in analisadas if r["analise"].get("efetivo") == "SIM"]
        base.update({
            "efetivas"        : len(efetivas),
            "efetividade_pct" : _pct(len(efetivas), len(analisadas)),
            "coaching_alta"   : _contar_coaching(analisadas, "ALTA")
        })

    elif area_key == "ATENDIMENTO":
        notas = [r["analise"].get("nota_final", 0) for r in analisadas]
        base.update({
            "nota_media"    : round(sum(notas) / len(notas), 1) if notas else 0,
            "acima_70"      : sum(1 for n in notas if n >= 70),
            "abaixo_50"     : sum(1 for n in notas if n < 50),
            "coaching_alta" : _contar_coaching(analisadas, "ALTA")
        })

    elif area_key == "COMERCIAL_CADASTRO":
        convertidas = [r for r in analisadas
                       if r["analise"].get("resultado_comercial", {}).get("status") == "CONVERTIDO"]
        base.update({
            "convertidas"   : len(convertidas),
            "conversao_pct" : _pct(len(convertidas), len(analisadas)),
            "coaching_alta" : _contar_coaching(analisadas, "ALTA")
        })

    return base


def _gestores_area(area_key, analisadas):
    agrupado = defaultdict(list)
    for r in analisadas:
        agrupado[r.get("agente", "Desconhecido")].append(r)

    resultado = []
    for agente, calls in agrupado.items():
        info = {"agente": agente, "total": len(calls)}

        if area_key == "SUCESSO_CORRETOR":
            ef = [c for c in calls if c["analise"].get("efetivo") == "SIM"]
            info.update({
                "efetivas"          : len(ef),
                "efetividade_pct"   : _pct(len(ef), len(calls)),
                "coaching_predominante": _moda([c["analise"].get("prioridade_coaching") for c in calls]),
                "spin_medio"        : _media_spin(calls)
            })

        elif area_key == "ATENDIMENTO":
            notas = [c["analise"].get("nota_final", 0) for c in calls]
            info.update({
                "nota_media"        : round(sum(notas) / len(notas), 1) if notas else 0,
                "coaching_predominante": _moda([c["analise"].get("prioridade_coaching") for c in calls]),
                "criterio_mais_falho": _criterio_mais_falho(calls)
            })

        elif area_key == "COMERCIAL_CADASTRO":
            cv = [c for c in calls
                  if c["analise"].get("resultado_comercial", {}).get("status") == "CONVERTIDO"]
            info.update({
                "convertidas"       : len(cv),
                "conversao_pct"     : _pct(len(cv), len(calls)),
                "coaching_predominante": _moda([c["analise"].get("prioridade_coaching") for c in calls]),
                "spin_medio"        : _media_spin(calls)
            })

        resultado.append(info)

    # Ordenar por métrica principal
    chave = {
        "SUCESSO_CORRETOR"  : "efetividade_pct",
        "ATENDIMENTO"       : "nota_media",
        "COMERCIAL_CADASTRO": "conversao_pct"
    }.get(area_key, "total")
    resultado.sort(key=lambda x: x.get(chave, 0), reverse=True)
    return resultado


def _resumo_ligacao(r, area_key):
    """Versão compacta de cada ligação para o Lovable."""
    base = {
        "id"               : r.get("ligacao_id"),
        "agente"           : r.get("agente"),
        "duracao_s"        : r.get("duracao"),
        "data"             : r.get("data"),
        "resumo"           : r["analise"].get("resumo"),
        "prioridade_coaching": r["analise"].get("prioridade_coaching"),
        "conformidade"     : r["analise"].get("conformidade", {}).get("status"),
        "boas_praticas"    : r["analise"].get("boas_praticas", []),
        "pontos_criticos"  : r["analise"].get("pontos_criticos",
                             r["analise"].get("pontos_desenvolvimento", []))
    }
    if area_key == "SUCESSO_CORRETOR":
        base["efetivo"]       = r["analise"].get("efetivo")
        base["impacto_receita"] = r["analise"].get("impacto_receita", {}).get("resultado")
        base["spin_aplicado"] = r["analise"].get("spin_aplicado", {})
    elif area_key == "ATENDIMENTO":
        base["nota_final"]    = r["analise"].get("nota_final")
        base["criterios"]     = r["analise"].get("criterios", {})
    elif area_key == "COMERCIAL_CADASTRO":
        base["resultado_comercial"] = r["analise"].get("resultado_comercial", {})
        base["tipo_contato"]  = r["analise"].get("tipo_contato")
        base["spin_aplicado"] = r["analise"].get("spin_aplicado", {})
    return base


# ── Dashboard geral ────────────────────────────────────────────────────────────

def gerar_consolidado_geral(relatorios, periodo, custo_total):
    """JSON da página 1 do Lovable (Dashboard Geral / Diretoria)."""
    total_lig = sum(r["consolidado"]["total_ligacoes"]  for r in relatorios.values())
    total_an  = sum(r["consolidado"]["analisadas"]      for r in relatorios.values())

    areas_resumo = {}
    for key, rel in relatorios.items():
        c = rel["consolidado"]
        areas_resumo[key] = {
            "area"          : rel["area"],
            "supervisor"    : rel["supervisor"],
            "total_ligacoes": c["total_ligacoes"],
            "analisadas"    : c["analisadas"],
            "cobertura_pct" : c["cobertura_pct"],
            # métrica principal de cada área
            "metrica_principal": (
                c.get("efetividade_pct") or
                c.get("nota_media") or
                c.get("conversao_pct") or 0
            ),
            "coaching_alta" : c.get("coaching_alta", 0),
            "custo_analise_usd": c["custo_analise_usd"]
        }

    return {
        "periodo"        : periodo,
        "gerado_em"      : datetime.now().isoformat(),
        "macro": {
            "total_ligacoes"    : total_lig,
            "total_analisadas"  : total_an,
            "cobertura_pct"     : _pct(total_an, total_lig),
            "custo_total_usd"   : round(custo_total, 4)
        },
        "areas": areas_resumo
    }


# ── Histórico de rodadas ───────────────────────────────────────────────────────

def registrar_historico(caminho_historico, data, resumo_por_area, custo_total):
    """
    Acrescenta uma entrada ao histórico de rodadas (para a seção
    'Histórico de Qualidade' do Lovable).
    """
    import os
    historico = []
    if os.path.exists(caminho_historico):
        with open(caminho_historico, "r", encoding="utf-8") as f:
            historico = json.load(f)

    entrada = {
        "data"             : data,
        "rodada_em"        : datetime.now().isoformat(),
        "custo_total_usd"  : round(custo_total, 4),
        "areas_processadas": resumo_por_area
    }
    historico.append(entrada)

    with open(caminho_historico, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pct(parte, total):
    return round(parte / total * 100, 1) if total else 0.0

def _moda(lista):
    lista = [x for x in lista if x]
    return Counter(lista).most_common(1)[0][0] if lista else "MEDIA"

def _contar_coaching(analisadas, nivel):
    return sum(1 for r in analisadas if r["analise"].get("prioridade_coaching") == nivel)

def _coletar_campo(analisadas, area_key, campo):
    items = []
    campo_atendimento = "pontos_desenvolvimento" if campo == "pontos_criticos" else "pontos_fortes"
    for r in analisadas:
        c = r["analise"].get(campo, r["analise"].get(campo_atendimento, []))
        items.extend(c if isinstance(c, list) else [c])
    return [str(i) for i in items if i]

def _top_itens(lista, n=6):
    contagem = Counter(lista)
    return [{"item": item, "ocorrencias": cnt}
            for item, cnt in contagem.most_common(n)]

def _media_spin(calls):
    """Calcula percentual médio de SPIN aplicado por agente."""
    scores = []
    for c in calls:
        spin = c["analise"].get("spin_aplicado", {})
        if spin:
            sim = sum(1 for v in spin.values() if v == "SIM")
            scores.append(sim / len(spin) * 100)
    return round(sum(scores) / len(scores), 1) if scores else 0

def _criterio_mais_falho(calls):
    """Retorna o critério com mais NAO_CUMPRIU no Atendimento."""
    falhas = Counter()
    for c in calls:
        for criterio, dados in c["analise"].get("criterios", {}).items():
            if dados.get("status") == "NAO_CUMPRIU":
                falhas[criterio] += 1
    return falhas.most_common(1)[0][0] if falhas else "N/A"
