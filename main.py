"""
Orquestrador principal do sistema de monitorias Ragaz.

Uso:
    python main.py                    → processa a pasta de hoje
    python main.py 2026-05-25         → processa data específica
    python main.py 2026-05-25 --estimar  → só mostra projeção de custo, não processa

Estrutura esperada em dados/:
    dados/
    └── 2026-05-25/
        ├── sucesso_corretor/
        │   ├── audios/          ← coloque os MP3 aqui
        │   └── relatorio.xlsx   ← export do Bitrix (opcional, enriquece contexto)
        ├── atendimento/
        │   ├── audios/
        │   └── relatorio.xlsx
        └── comercial_cadastro/
            ├── audios/
            └── relatorio.xlsx
"""

import os
import sys
import json
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


# ── Processar uma área ─────────────────────────────────────────────────────────

def processar_area(area_key, pasta_dia):
    cfg          = AREAS[area_key]
    pasta_area   = os.path.join(pasta_dia, cfg["pasta"])
    pasta_audios = os.path.join(pasta_area, "audios")

    if not os.path.exists(pasta_audios):
        print(f"    Pasta nao encontrada: {pasta_audios} — pulando.")
        return [], 0.0

    audios = sorted(Path(pasta_audios).glob("*.mp3"))
    if not audios:
        print(f"    Nenhum MP3 encontrado em {pasta_audios} — pulando.")
        return [], 0.0

    print(f"    {len(audios)} audio(s) encontrado(s)")

    # Carregar Excel se existir
    df = None
    excel_path = os.path.join(pasta_area, "relatorio.xlsx")
    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path)
        print(f"    Excel carregado: {len(df)} linhas")

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

        # Agente e contexto
        agente  = _detectar_agente(audio_path.name, cfg["agentes"])
        contexto = _montar_contexto(agente, duracao, df, audio_path.name)

        # Transcrição
        texto, erro = transcrever_audio(str(audio_path))
        if erro or not texto.strip():
            print(f"FALHA TRANSCRIÇÃO: {erro or 'vazio'}")
            resultados.append({
                "ligacao_id": audio_path.stem,
                "agente"    : agente,
                "duracao"   : round(duracao),
                "data"      : datetime.now().strftime("%Y-%m-%d"),
                "arquivo"   : audio_path.name,
                "sucesso"   : False,
                "erro"      : erro or "transcrição vazia"
            })
            continue

        # Análise
        resultado = analisar_ligacao(texto, contexto, area_key)
        resultado.update({
            "ligacao_id": audio_path.stem,
            "agente"    : agente,
            "duracao"   : round(duracao),
            "data"      : datetime.now().strftime("%Y-%m-%d"),
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
    print("  SISTEMA DE MONITORIAS RAGAZ")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Argumentos
    data     = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    so_estimar = "--estimar" in sys.argv

    pasta_dia    = os.path.join(DADOS_DIR, data)
    pasta_output = os.path.join(OUTPUT_DIR, data)
    os.makedirs(pasta_output, exist_ok=True)

    print(f"\n  Data processada : {data}")
    print(f"  Pasta de dados  : {pasta_dia}")
    print(f"  Saida           : {pasta_output}")

    if not os.path.exists(pasta_dia):
        print(f"\n  ERRO: Pasta {pasta_dia} nao encontrada.")
        print("  Crie a estrutura abaixo e coloque os MP3s:")
        for cfg in AREAS.values():
            print(f"    dados/{data}/{cfg['pasta']}/audios/")
        return

    # Contar áudios para estimativa
    total_audios = 0
    for cfg in AREAS.values():
        p = Path(os.path.join(pasta_dia, cfg["pasta"], "audios"))
        if p.exists():
            total_audios += len(list(p.glob("*.mp3")))

    if total_audios == 0:
        print("\n  Nenhum MP3 encontrado em nenhuma área.")
        return

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

    for area_key, cfg in AREAS.items():
        print(f"\n[{cfg['nome'].upper()}]  supervisor: {cfg['supervisor']}")
        resultados, custo = processar_area(area_key, pasta_dia)
        custo_total += custo

        if not resultados:
            continue

        periodo  = data[:7]   # YYYY-MM
        relatorio = gerar_relatorio_area(area_key, resultados, periodo, custo)
        relatorios[area_key] = relatorio

        # Salvar JSON da área
        nome_json = f"relatorio_{cfg['pasta']}_{data}.json"
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
        consolidado = gerar_consolidado_geral(relatorios, data[:7], custo_total)
        nome_cons   = f"consolidado_{data}.json"
        with open(os.path.join(pasta_output, nome_cons), "w", encoding="utf-8") as f:
            json.dump(consolidado, f, ensure_ascii=False, indent=2)

        # Histórico
        registrar_historico(
            os.path.join(OUTPUT_DIR, "historico.json"),
            data, resumo_hist, custo_total
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
