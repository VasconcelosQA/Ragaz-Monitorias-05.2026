"""
Transcrição de áudios MP3.

Método atual: Google Speech Recognition (gratuito, sem chave de API).
Limitação: menos preciso em áudios com ruído, limite de taxa de requisições.

Alternativa recomendada se o volume travar: OpenAI Whisper local (grátis, roda offline).
Para ativar Whisper: pip install openai-whisper e trocar a função transcrever_audio.
"""

import os
import subprocess
import speech_recognition as sr
from mutagen.mp3 import MP3
from config import DURACAO_MINIMA_SEGUNDOS, IDIOMA_TRANSCRICAO
from config import PRECO_HAIKU_INPUT, PRECO_HAIKU_OUTPUT, PRECO_SONNET_INPUT, PRECO_SONNET_OUTPUT


def obter_duracao_mp3(caminho):
    """Retorna duração do MP3 em segundos."""
    try:
        audio = MP3(caminho)
        return audio.info.length
    except Exception:
        try:
            import librosa
            y, sr_rate = librosa.load(caminho, sr=None, duration=1)
            # fallback simples
            return os.path.getsize(caminho) / 16000
        except Exception:
            return 0


def transcrever_audio(caminho_mp3):
    """
    Transcreve MP3 usando Google Speech Recognition.
    Retorna (texto, erro).  erro=None se OK.
    """
    recognizer = sr.Recognizer()
    wav_temp = caminho_mp3.replace(".mp3", "_tmp.wav")

    try:
        # Converter MP3 → WAV mono 16kHz (formato aceito pelo Google SR)
        result = subprocess.run(
            ["ffmpeg", "-i", caminho_mp3,
             "-ar", "16000", "-ac", "1",
             wav_temp, "-y", "-loglevel", "quiet"],
            capture_output=True
        )
        if result.returncode != 0:
            return "", "ffmpeg falhou — verifique se está instalado"

        with sr.AudioFile(wav_temp) as source:
            audio = recognizer.record(source)

        texto = recognizer.recognize_google(audio, language=IDIOMA_TRANSCRICAO)
        return texto, None

    except sr.UnknownValueError:
        return "", "Áudio não reconhecido (silêncio ou ruído)"
    except sr.RequestError as e:
        return "", f"Erro Google API: {e}"
    except Exception as e:
        return "", f"Erro inesperado: {e}"
    finally:
        if os.path.exists(wav_temp):
            os.remove(wav_temp)


def estimar_custo_analise(n_ligacoes, duracao_media_min=3.0):
    """
    Projeta custo de análise Claude para N ligações.

    IMPORTANTE: Claude (Haiku/Sonnet) analisa TEXTO, não áudio.
    A transcrição em si é feita pelo Google SR (gratuito) ou Whisper (local, gratuito).
    Esta estimativa é só para o custo da análise IA.

    Custo de transcrição com Whisper API (OpenAI) se quiser comparar:
    - $0.006 por minuto de áudio
    - Para 500 ligações de 3 min: $0.006 * 3 * 500 = $9.00
    """
    # ~150 palavras por minuto de áudio → ~200 tokens
    tokens_transcricao_por_ligacao = int(duracao_media_min * 200)
    tokens_prompt_fixo              = 350   # instrução + contexto
    tokens_input_por_ligacao        = tokens_transcricao_por_ligacao + tokens_prompt_fixo
    tokens_output_por_ligacao       = 450   # JSON de resposta

    total_input  = n_ligacoes * tokens_input_por_ligacao
    total_output = n_ligacoes * tokens_output_por_ligacao

    custo_haiku  = total_input * PRECO_HAIKU_INPUT  + total_output * PRECO_HAIKU_OUTPUT
    custo_sonnet = total_input * PRECO_SONNET_INPUT + total_output * PRECO_SONNET_OUTPUT

    custo_whisper_api = n_ligacoes * duracao_media_min * 0.006  # OpenAI Whisper API

    return {
        "n_ligacoes"            : n_ligacoes,
        "duracao_media_min"     : duracao_media_min,
        "tokens_input_total"    : total_input,
        "tokens_output_total"   : total_output,
        "analise_haiku_usd"     : round(custo_haiku,  4),
        "analise_sonnet_usd"    : round(custo_sonnet, 4),
        "economia_haiku_pct"    : round((1 - custo_haiku / custo_sonnet) * 100, 1),
        "transcricao_google_usd": 0.0,             # grátis
        "transcricao_whisper_api_usd": round(custo_whisper_api, 2),  # se usar OpenAI
        "total_haiku_google_usd": round(custo_haiku, 4),
        "total_haiku_whisper_usd": round(custo_haiku + custo_whisper_api, 4),
    }
