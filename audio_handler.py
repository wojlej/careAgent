# audio_handler.py

import base64
import asyncio
from typing import Optional

from openai import AsyncOpenAI
from openai.helpers import LocalAudioPlayer

import config

# inicjalizacja asynchronicznego klienta
async_openai = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

async def _play_text_async(text: str) -> None:
    """Odtwarza audio strumieniowo na backendzie."""
    async with async_openai.audio.speech.with_streaming_response.create(
        model=config.OPENAI_TTS_MODEL,
        voice=config.OPENAI_TTS_VOICE,
        input=text,
        instructions="Speak in a cheerful and positive tone.",
        response_format="pcm",
    ) as response:
        await LocalAudioPlayer().play(response)

async def _collect_pcm_async(text: str) -> bytes:
    """
    Pobiera cały PCM w jednym kawałku – bez iterowania po strumieniu.
    """
    # wywołanie bez streaming_response zwraca AsyncStreamedBinaryAPIResponse
    resp = await async_openai.audio.speech.create(
        model=config.OPENAI_TTS_MODEL,
        voice=config.OPENAI_TTS_VOICE,
        input=text,
        instructions="Speak in a cheerful and positive tone.",
        response_format="pcm",
    )

    if hasattr(resp, "aread"):
        return await resp.aread()
    # albo zwykły read (synchronous)
    if hasattr(resp, "read"):
        return resp.read()
    # albo już bytes
    if isinstance(resp, (bytes, bytearray)):
        return resp

    raise TypeError(f"Nie można przekonwertować {type(resp)} na bytes")

def handle_audio(text: str, play_on = None) -> Optional[str]:
    """
    Jeśli config.PLAY_ON_BACKEND jest True:
      – odtwarza audio na serwerze i zwraca None.
    W przeciwnym razie:
      – zwraca Base64 strumienia PCM do wysłania front-endowi.
    """
    if config.PLAY_ON_BACKEND or play_on:
        asyncio.run(_play_text_async(text))
        return None
    else:
        pcm_bytes = asyncio.run(_collect_pcm_async(text))
        return base64.b64encode(pcm_bytes).decode('utf-8')
