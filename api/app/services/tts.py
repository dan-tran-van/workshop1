from collections import OrderedDict
import hashlib
import logging
import threading
from typing import Tuple

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, OpenAIError

from app.config import settings

logger = logging.getLogger(__name__)

MAX_TTS_TEXT_LENGTH = 2000
TTS_CACHE_MAX_ITEMS = 64

_tts_cache_lock = threading.Lock()
_tts_cache: "OrderedDict[tuple[str, ...], tuple[bytes, str]]" = OrderedDict()


class TTSError(Exception):
    """Base error for text-to-speech synthesis failures."""


class TTSNotConfiguredError(TTSError):
    """Raised when the selected TTS provider is not configured."""


class TTSTimeoutError(TTSError):
    """Raised when a TTS request times out."""


class TTSUpstreamError(TTSError):
    """Raised when a TTS provider returns an unexpected error."""


def clear_tts_cache() -> None:
    """Clear the in-memory TTS audio cache (used for test isolation)."""
    with _tts_cache_lock:
        _tts_cache.clear()


def _normalize_tts_text(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise ValueError("Summary text is empty")
    return cleaned[:MAX_TTS_TEXT_LENGTH]


def _get_cached_audio(cache_key: tuple[str, ...]) -> Tuple[bytes, str] | None:
    with _tts_cache_lock:
        cached = _tts_cache.get(cache_key)
        if cached is not None:
            _tts_cache.move_to_end(cache_key)
        return cached


def _store_cached_audio(cache_key: tuple[str, ...], audio_bytes: bytes, media_type: str) -> None:
    with _tts_cache_lock:
        _tts_cache[cache_key] = (audio_bytes, media_type)
        _tts_cache.move_to_end(cache_key)
        while len(_tts_cache) > TTS_CACHE_MAX_ITEMS:
            _tts_cache.popitem(last=False)


def _extract_audio_payload(response: httpx.Response, source_label: str, default_media_type: str) -> Tuple[bytes, str]:
    audio_bytes = response.content or b""
    raw_content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if not audio_bytes or raw_content_type.startswith(("application/json", "text/")):
        logger.warning("%s returned non-audio response (content_type=%s)", source_label, raw_content_type)
        raise TTSUpstreamError("Unexpected response format from text-to-speech provider.")
    media_type = raw_content_type if raw_content_type.startswith("audio/") else default_media_type
    return audio_bytes, media_type


def _normalize_wav_sizes(audio_bytes: bytes) -> bytes:
    if len(audio_bytes) < 12 or audio_bytes[:4] != b"RIFF" or audio_bytes[8:12] != b"WAVE":
        raise TTSUpstreamError("OpenAI TTS returned an invalid WAV response.")
    if len(audio_bytes) - 8 > 0xFFFFFFFF:
        raise TTSUpstreamError("OpenAI TTS returned an oversized WAV response.")

    normalized = bytearray(audio_bytes)
    normalized[4:8] = (len(audio_bytes) - 8).to_bytes(4, "little")
    offset = 12

    while offset + 8 <= len(normalized):
        chunk_id = normalized[offset:offset + 4]
        chunk_size = int.from_bytes(normalized[offset + 4:offset + 8], "little")
        payload_offset = offset + 8
        available_size = len(normalized) - payload_offset

        if chunk_id == b"data":
            if chunk_size == 0xFFFFFFFF or chunk_size > available_size:
                normalized[offset + 4:offset + 8] = available_size.to_bytes(4, "little")
            return bytes(normalized)

        if chunk_size > available_size:
            break
        offset = payload_offset + chunk_size + (chunk_size & 1)

    raise TTSUpstreamError("OpenAI TTS returned a WAV response without an audio data chunk.")


def _synthesize_with_openai(cleaned: str, text_hash: str) -> Tuple[bytes, str]:
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        raise TTSNotConfiguredError("OpenAI TTS is not configured on the server.")

    model = (settings.OPENAI_TTS_MODEL or "gpt-4o-mini-tts").strip() or "gpt-4o-mini-tts"
    voice = (settings.OPENAI_TTS_VOICE or "coral").strip() or "coral"
    cache_key = ("openai", model, voice, text_hash)
    cached = _get_cached_audio(cache_key)
    if cached is not None:
        return cached

    try:
        client = OpenAI(api_key=api_key, timeout=settings.OPENAI_TTS_TIMEOUT)
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=cleaned,
            response_format="wav",
        )
    except APITimeoutError as exc:
        logger.warning("OpenAI TTS request timed out for model=%s", model)
        raise TTSTimeoutError("Text-to-speech request timed out. Please try again.") from exc
    except APIConnectionError as exc:
        logger.warning("OpenAI TTS connection error for model=%s", model)
        raise TTSUpstreamError("Unable to reach the text-to-speech provider.") from exc
    except APIStatusError as exc:
        logger.warning("OpenAI TTS failed for model=%s with status=%s", model, exc.status_code)
        raise TTSUpstreamError("Text-to-speech service returned an error.") from exc
    except OpenAIError as exc:
        logger.warning("OpenAI TTS failed for model=%s (%s)", model, type(exc).__name__)
        raise TTSUpstreamError("Text-to-speech service returned an error.") from exc

    audio_bytes = response.content or b""
    if not audio_bytes:
        logger.warning("OpenAI TTS returned an empty audio response for model=%s", model)
        raise TTSUpstreamError("Text-to-speech service returned an empty audio response.")
    try:
        audio_bytes = _normalize_wav_sizes(audio_bytes)
    except TTSUpstreamError:
        logger.warning("OpenAI TTS returned an invalid WAV response for model=%s", model)
        raise

    result = (audio_bytes, "audio/wav")
    _store_cached_audio(cache_key, *result)
    return result


def _synthesize_with_compatible_endpoint(cleaned: str, text_hash: str, base_url: str) -> Tuple[bytes, str]:
    normalized_base = base_url.rstrip("/")
    model = (settings.TTS_MODEL or "kokoro").strip() or "kokoro"
    voice = (settings.TTS_VOICE or "af_heart").strip() or "af_heart"
    cache_key = ("kokoro", normalized_base, model, voice, text_hash)
    cached = _get_cached_audio(cache_key)
    if cached is not None:
        return cached

    try:
        response = httpx.post(
            f"{normalized_base}/v1/audio/speech",
            headers={"Accept": "audio/*"},
            json={
                "model": model,
                "input": cleaned,
                "voice": voice,
                "response_format": "mp3",
            },
            timeout=settings.TTS_ENDPOINT_TIMEOUT,
        )
    except httpx.TimeoutException as exc:
        logger.warning("Kokoro TTS endpoint timed out for model=%s", model)
        raise TTSTimeoutError("Text-to-speech request timed out. Please try again.") from exc
    except httpx.HTTPError as exc:
        logger.warning("Kokoro TTS transport error: %s", type(exc).__name__)
        raise TTSUpstreamError("Unable to reach the text-to-speech provider.") from exc

    if response.status_code != 200:
        logger.warning("Kokoro TTS endpoint failed with status=%s", response.status_code)
        raise TTSUpstreamError("Text-to-speech service returned an error.")

    result = _extract_audio_payload(response, f"Kokoro TTS model={model}", "audio/mpeg")
    _store_cached_audio(cache_key, *result)
    return result


def synthesize_speech(text: str) -> Tuple[bytes, str]:
    """Synthesize speech using OpenAI by default or a configured Kokoro endpoint."""
    cleaned = _normalize_tts_text(text)
    text_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    provider = (settings.TTS_PROVIDER or "openai").strip().lower()

    if provider == "openai":
        return _synthesize_with_openai(cleaned, text_hash)
    if provider == "kokoro":
        base_url = (settings.TTS_BASE_URL or "").strip()
        if not base_url:
            raise TTSNotConfiguredError("The Kokoro TTS endpoint is not configured.")
        return _synthesize_with_compatible_endpoint(cleaned, text_hash, base_url)

    raise TTSNotConfiguredError("The configured text-to-speech provider is not supported.")
