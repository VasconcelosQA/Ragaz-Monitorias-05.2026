"""
Orquestrador principal do sistema de monitorias Ragaz - VERSÃO FLEXÍVEL.

Uso:
    python main.py                    → processa todos os MP3s em dados/
    python main.py --estimar         → só mostra projeção de custo, não processa

Os audios estão em dados/ (raiz) e serão agrupados por área automaticamente
usando o mapeamento de colaboradores do config.py.
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
import pandas as pd

from config import (
    AREAS, DADOS_DIR, OUTPUT_DIR,
    DURACAO_MINIMA_SEGUNDOS,
    PRECO_HAIKU_INPUT, PRECO_HAIKU_OUTPUT
)
from transcriber import transcrever_audio, obter_duracao_mp3, estimar_custo_analise
from analyzer import analisar_ligacao
from reporter import (
    gerar_relatorio_area,
    gerar_consolidado_geral,
    registrar_historico
)


# ── Mapear colaborador → área ─────────────────────────────────────────────────

def mapear_colaborador_para_area(colaborador):
    """Identifica a área de um colaborador usando o config.py."""
    if not colaborador:
        return None

    colaborador_lower = colaborador.lower().strip()

    for area_key, cfg in AREAS.items():
        for agente in cfg["agentes"]:
            if agente.lower() in colaborador_lower or colaborador_lower in agente.lower():
                return area_key
    return None


def carregar_mapeamento_telefone_area():
    """Lê o Excel e cria dois mapas:
    - telefone → área
    - telefone → nome do colaborador (para identificar o gestor)
    """
    excel_path = os.path.join(DADOS_DIR, "calls_detail_20260525_378585bd_6a1495af09ba6.xls")

    if not os.path.exists(excel_path):
        print(f"    Aviso: Excel não encontrado ({excel_path})")
        return {}, {}

    try:
        dfs = pd.read_html(excel_path)
        if not dfs:
            return {}, {}

        df = dfs[0]
        telefone_para_area = {}
        telefone_para_gestor = {}

        for idx, row in df.iterrows():
            if pd.isna(row.get('Colaborador')):
                continue

            colaborador = str(row['Colaborador']).strip()
            area = mapear_colaborador_para_area(colaborador)
            if not area:
                continue

            telefone_col = 'Telefone'
            if telefone_col not in df.columns:
                continue

            telefone_str = str(row[telefone_col]).strip()
            if not telefone_str or telefone_str == 'N/A':
                continue

            tel_norm = normalizar_telefone(telefone_str)
            if tel_norm:
                telefone_para_area[tel_norm] = area
                telefone_para_gestor[tel_norm] = colaborador

        return telefone_para_area, telefone_para_gestor

    except Exception as e:
        print(f"    Erro ao ler Excel: {e}")
        return {}, {}


def normalizar_telefone(tel):
    """Normaliza telefone removendo caracteres especiais."""
    if not tel or tel == 'N/A':
        return None
    tel_str = str(tel).replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').strip()
    # Remover leading zeros se houver
    return tel_str.lstrip('0') if tel_str else None


def encontrar_audios_por_area():
    """Encontra todos os MP3s em dados/ e agrupa por área usando Excel como referência."""
    audios_por_area = {area_key: [] for area_key in AREAS.keys()}

    if not os.path.exists(DADOS_DIR):
        return audios_por_area

    # Carregar mapa telefone → área e gestor
    telefone_para_area, telefone_para_gestor = carregar_mapeamento_telefone_area()

    audios = sorted(Path(DADOS_DIR).glob("*.mp3"))

    print(f"    Mapeamento: {len(telefone_para_area)} telefones mapeados para áreas")

    for audio_path in audios:
        nome_arquivo = audio_path.name
        area_encontrada = None

        # Extrair telefone do nome do arquivo
        match = re.search(r'[\+]?(\d{10,15})', nome_arquivo)
        if match:
            tel_norm = normalizar_telefone(match.group(1))
            if tel_norm in telefone_para_area:
                area_encontrada = telefone_para_area[tel_norm]

        if area_encontrada:
            audios_por_area[area_encontrada].append(audio_path)

    return audios_por_area, telefone_para_gestor


# ── Processar uma área ─────────────────────────────────────────────────────────

def processar_area(area_key, audios_area, telefone_para_gestor):
    cfg = AREAS[area_key]

    if not audios_area:
        print(f"    Nenhum MP3 encontrado para esta área — pulando.")
        return [], 0.0

    # Pasta para salvar transcrições
    pasta_transcricoes = os.path.join(os.path.dirname(DADOS_DIR), "transcricoes")
    os.makedirs(pasta_transcricoes, exist_ok=True)

    audios = sorted(audios_area)
    print(f"    {len(audios)} audio(s) encontrado(s)")

    resultados          = []
    total_tokens_input  = 0
    total_tokens_output = 0

    for i, audio_path in enumerate(audios, 1):
        print(f"    [{i:>3}/{len(audios)}] {audio_path.name}", end="  ", flush=True)

        # Duração
        duracao = obter_duracao_mp3(str(audio_path))
        if duracao < DURACAO_MINIMA_SEGUNDOS:
            print(f"IGNORADO ({duracao:.0f}s < mínimo)")
            continue

        # Identificar gestor pelo telefone (via Excel) — muito mais confiável
        match = re.search(r'[\+]?(\d{10,15})', audio_path.name)
        tel_norm = normalizar_telefone(match.group(1)) if match else None
        agente = telefone_para_gestor.get(tel_norm, "Desconhecido") if tel_norm else "Desconhecido"

        # call_id para salvar transcrição
        call_id = audio_path.stem.replace(" ", "_")
        arquivo_transcricao = os.path.join(pasta_transcricoes, f"{call_id}.txt")

        # Contexto
        contexto = {
            "gestor": agente,
            "telefone": tel_norm or "N/A",
            "tipo_pendencia": "N/A",
            "duracao": round(duracao)
        }

        # Transcrição — usa cache se já existir
        if os.path.exists(arquivo_transcricao):
            with open(arquivo_transcricao, encoding='utf-8') as f:
                texto = f.read().strip()
            erro = None
        else:
            texto, erro = transcrever_audio(str(audio_path))
            # Salvar transcrição para reuso futuro
            if texto and not erro:
                with open(arquivo_transcricao, 'w', encoding='utf-8') as f:
                    f.write(texto)

        # Extrair data real do nome do arquivo (ex: "2026-05-11 15-56-52 +55...")
        data_match = re.search(r'(\d{4}-\d{2}-\d{2})', audio_path.name)
        data_ligacao = data_match.group(1) if data_match else datetime.now().strftime("%Y-%m-%d")

        if erro or not texto.strip():
            print(f"FALHA TRANSCRIÇÃO: {erro or 'vazio'}")
            resultados.append({
                "ligacao_id": audio_path.stem,
                "agente"    : agente,
                "duracao"   : round(duracao),
                "data"      : data_ligacao,
                "arquivo"   : audio_path.name,
                "sucesso"   : False,
                "erro"      : erro or "transcrição vazia"
            })
            continue

        # Truncar texto longo para reduzir tokens (max ~1500 palavras)
        palavras = texto.split()
        if len(palavras) > 1500:
            texto = ' '.join(palavras[:1500]) + '...'

        # Análise
        resultado = analisar_ligacao(texto, contexto, area_key)
        resultado.update({
            "ligacao_id": audio_path.stem,
            "agente"    : agente,
            "duracao"   : round(duracao),
            "data"      : data_ligacao,
            "arquivo"   : audio_path.name
        })

        if resultado["sucesso"]:
            total_tokens_input  += resultado.get("tokens_input",  0)
            total_tokens_output += resultado.get("tokens_output", 0)
            # Exibir resultado principal
            a = resultado["analise"]
            metrica = (
                a.get("efetivo") or
                str(a.get("nota_final", "")) or
                a.get("resultado_comercial", {}).get("status", "-")
            )
            coaching = a.get("prioridade_coaching", "-")
            print(f"OK  {metrica:<10} coaching:{coaching}")
        else:
            print(f"ERRO ANÁLISE: {resultado.get('erro')}")

        resultados.append(resultado)

    # Custo real da área
    custo = (total_tokens_input  * PRECO_HAIKU_INPUT +
             total_tokens_output * PRECO_HAIKU_OUTPUT)
    print(f"    Custo: ${custo:.4f}  |  "
          f"tokens: {total_tokens_input}in / {total_tokens_output}out")

    return resultados, custo


# ── Detectar agente pelo nome do arquivo ───────────────────────────────────────

def _detectar_agente(nome_arquivo, agentes):
    """Tenta identificar o agente pelo nome do arquivo MP3."""
    lower = nome_arquivo.lower()
    for agente in agentes:
        # normaliza para comparação (remove acentos simples)
        agente_norm = agente.lower() \
            .replace("ã", "a").replace("á", "a").replace("â", "a") \
            .replace("é", "e").replace("ê", "e") \
            .replace("í", "i") \
            .replace("ó", "o").replace("ô", "o") \
            .replace("ú", "u") \
            .replace("ç", "c")
        if agente_norm in lower or agente.lower() in lower:
            return agente
    return "Desconhecido"


# ── Contexto a partir do Excel ─────────────────────────────────────────────────

def _montar_contexto(agente, duracao, df, nome_arquivo):
    ctx = {
        "gestor"         : agente,
        "telefone"       : "N/A",
        "tipo_pendencia" : "N/A",
        "duracao"        : round(duracao)
    }
    if df is None:
        return ctx

    # Tentar encontrar linha pelo nome do agente
    for col in df.columns:
        col_lower = col.lower()
        if any(k in col_lower for k in ["nome", "agente", "gestor", "usuario"]):
            mask = df[col].astype(str).str.lower().str.contains(
                agente.lower(), na=False
            )
            if mask.any():
                row = df[mask].iloc[0]
                for c in df.columns:
                    cl = c.lower()
                    if "telefone" in cl or "fone" in cl or "numero" in cl:
                        ctx["telefone"] = str(row[c])
                    if "tipo" in cl or "pendencia" in cl or "pendência" in cl:
                        ctx["tipo_pendencia"] = str(row[c])
                break
    return ctx


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  SISTEMA DE MONITORIAS RAGAZ - VERSÃO FLEXÍVEL")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    so_estimar = "--estimar" in sys.argv
    pasta_output = os.path.join(OUTPUT_DIR, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(pasta_output, exist_ok=True)

    print(f"\n  Pasta de dados  : {DADOS_DIR}")
    print(f"  Saida           : {pasta_output}")

    # Encontrar áudios agrupados por área
    print(f"\n  Carregando mapeamento de colaboradores...")
    audios_por_area, telefone_para_gestor = encontrar_audios_por_area()

    # Contar total
    total_audios = sum(len(v) for v in audios_por_area.values())

    if total_audios == 0:
        print("\n  ERRO: Nenhum MP3 encontrado em dados/")
        return

    print(f"  Total de audios encontrados: {total_audios}")
    for area_key, audios in audios_por_area.items():
        if audios:
            print(f"    {AREAS[area_key]['nome']}: {len(audios)} arquivo(s)")

    # Estimativa de custo
    est = estimar_custo_analise(total_audios)
    print(f"\n  Estimativa ({total_audios} audios, ~3 min cada):")
    print(f"    Transcricao Google SR : GRÁTIS")
    print(f"    Analise Haiku         : ${est['analise_haiku_usd']:.4f}")
    print(f"    Analise Sonnet        : ${est['analise_sonnet_usd']:.4f}")
    print(f"    Economia com Haiku    : {est['economia_haiku_pct']}%")
    print(f"    (Whisper API OpenAI, se usar): ${est['transcricao_whisper_api_usd']:.2f}")

    if so_estimar:
        print("\n  Modo --estimar: nenhum processamento realizado.")
        return

    # Processar cada área
    relatorios  = {}
    custo_total = 0.0
    resumo_hist = {}
    data_processamento = datetime.now().strftime("%Y-%m-%d")

    for area_key, cfg in AREAS.items():
        if not audios_por_area[area_key]:
            continue

        print(f"\n[{cfg['nome'].upper()}]  supervisor: {cfg['supervisor']}")
        resultados, custo = processar_area(area_key, audios_por_area[area_key], telefone_para_gestor)
        custo_total += custo

        if not resultados:
            continue

        periodo = data_processamento[:7]
        relatorio = gerar_relatorio_area(area_key, resultados, periodo, custo)
        relatorios[area_key] = relatorio

        # Salvar JSON da área
        nome_json = f"relatorio_{cfg['pasta']}_{data_processamento}.json"
        with open(os.path.join(pasta_output, nome_json), "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2)

        print(f"    Salvo: {nome_json}")

        # Resumo para histórico
        c = relatorio["consolidado"]
        resumo_hist[area_key] = {
            "total_analisadas": c["analisadas"],
            "metrica_principal": (
                c.get("efetividade_pct") or
                c.get("nota_media") or
                c.get("conversao_pct") or 0
            )
        }

    # Consolidado geral
    if relatorios:
        consolidado = gerar_consolidado_geral(relatorios, periodo, custo_total)
        nome_cons = f"consolidado_{data_processamento}.json"
        with open(os.path.join(pasta_output, nome_cons), "w", encoding="utf-8") as f:
            json.dump(consolidado, f, ensure_ascii=False, indent=2)

        # Histórico
        registrar_historico(
            os.path.join(OUTPUT_DIR, "historico.json"),
            data_processamento, resumo_hist, custo_total
        )

        print(f"\n{'='*70}")
        print(f"  Custo total da rodada : ${custo_total:.4f}")
        print(f"  Arquivos gerados em   : {pasta_output}")
        print(f"  Consolidado           : {nome_cons}")
        print(f"{'='*70}")
    else:
        print("\n  Nenhuma área processada com sucesso.")


if __name__ == "__main__":
    main()
