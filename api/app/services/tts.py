from collections import OrderedDict
import hashlib
import logging
import threading
import time
from typing import Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

MAX_TTS_TEXT_LENGTH = 2000
TTS_CACHE_MAX_ITEMS = 64
COLD_START_MAX_RETRY_WAIT_SECONDS = 5.0

_tts_cache_lock = threading.Lock()
_tts_cache: "OrderedDict[tuple[str, str], tuple[bytes, str]]" = OrderedDict()


class TTSError(Exception):
    """Base error for Text-to-Speech synthesis failures."""


class TTSNotConfiguredError(TTSError):
    """Raised when the Hugging Face API token is missing."""


class TTSModelLoadingError(TTSError):
    """Raised when the Hugging Face TTS model is warming up."""


class TTSTimeoutError(TTSError):
    """Raised when the Hugging Face TTS request times out."""


class TTSUpstreamError(TTSError):
    """Raised when the Hugging Face TTS provider returns an unexpected error."""


def clear_tts_cache() -> None:
    """Clear the in-memory TTS audio cache (used for test isolation)."""
    with _tts_cache_lock:
        _tts_cache.clear()


def _normalize_tts_text(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise ValueError("Summary text is empty")
    return cleaned[:MAX_TTS_TEXT_LENGTH]


def _extract_estimated_time(response: httpx.Response) -> float:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            estimated = payload.get("estimated_time")
            if isinstance(estimated, (int, float)):
                return float(estimated)
    except Exception:
        pass
    return 0.0


def _get_cached_audio(cache_key: tuple[str, str]) -> Tuple[bytes, str] | None:
    with _tts_cache_lock:
        cached = _tts_cache.get(cache_key)
        if cached is not None:
            _tts_cache.move_to_end(cache_key)
        return cached


def _store_cached_audio(cache_key: tuple[str, str], audio_bytes: bytes, media_type: str) -> None:
    with _tts_cache_lock:
        _tts_cache[cache_key] = (audio_bytes, media_type)
        _tts_cache.move_to_end(cache_key)
        while len(_tts_cache) > TTS_CACHE_MAX_ITEMS:
            _tts_cache.popitem(last=False)


def _extract_audio_payload(response: httpx.Response, source_label: str, default_media_type: str) -> Tuple[bytes, str]:
    audio_bytes = response.content or b""
    raw_content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if not audio_bytes or raw_content_type.startswith("application/json") or raw_content_type.startswith("text/"):
        logger.warning("%s returned non-audio response (content_type=%s)", source_label, raw_content_type)
        raise TTSUpstreamError("Unexpected response format from text-to-speech provider.")
    media_type = raw_content_type if raw_content_type.startswith("audio/") else default_media_type
    return audio_bytes, media_type


def _synthesize_with_openai_endpoint(cleaned: str, text_hash: str, base_url: str) -> Tuple[bytes, str]:
    normalized_base = base_url.rstrip("/")
    tts_model = (settings.TTS_MODEL or "kokoro").strip() or "kokoro"
    tts_voice = (settings.TTS_VOICE or "af_heart").strip() or "af_heart"
    cache_key = (f"openai-tts:{normalized_base}:{tts_model}:{tts_voice}", text_hash)

    cached = _get_cached_audio(cache_key)
    if cached is not None:
        return cached

    url = f"{normalized_base}/v1/audio/speech"
    payload = {
        "model": tts_model,
        "input": cleaned,
        "voice": tts_voice,
        "response_format": "mp3",
    }

    try:
        response = httpx.post(
            url,
            headers={"Accept": "audio/*"},
            json=payload,
            timeout=settings.HUGGINGFACE_TTS_TIMEOUT,
        )
    except httpx.TimeoutException as exc:
        logger.warning("TTS endpoint request timed out for model=%s", tts_model)
        raise TTSTimeoutError("Text-to-speech request timed out. Please try again.") from exc
    except httpx.HTTPError as exc:
        logger.warning("TTS endpoint transport error for model=%s: %s", tts_model, type(exc).__name__)
        raise TTSUpstreamError("Unable to reach text-to-speech provider.") from exc

    if response.status_code != 200:
        logger.warning("TTS endpoint failed for model=%s with status=%s", tts_model, response.status_code)
        raise TTSUpstreamError("Text-to-speech service returned an error.")

    audio_bytes, media_type = _extract_audio_payload(response, f"TTS endpoint model={tts_model}", "audio/mpeg")
    _store_cached_audio(cache_key, audio_bytes, media_type)
    return audio_bytes, media_type


def synthesize_speech(text: str) -> Tuple[bytes, str]:
    """
    Convert analysis summary text to speech bytes using either a configured OpenAI-compatible
    TTS endpoint (TTS_BASE_URL, e.g. local Kokoro Docker / Cloudflare Tunnel) or Hugging Face
    Inference API. Caches synthesized audio in a bounded thread-safe LRU cache.
    """
    cleaned = _normalize_tts_text(text)
    text_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    tts_base_url = (settings.TTS_BASE_URL or "").strip()
    if tts_base_url:
        return _synthesize_with_openai_endpoint(cleaned, text_hash, tts_base_url)

    token = (settings.HUGGINGFACE_API_TOKEN or "").strip()
    if not token:
        raise TTSNotConfiguredError("Text-to-speech is not configured on the server.")

    model = (settings.HUGGINGFACE_TTS_MODEL or "facebook/mms-tts-eng").strip() or "facebook/mms-tts-eng"
    cache_key = (model, text_hash)

    cached = _get_cached_audio(cache_key)
    if cached is not None:
        return cached

    base_url = (settings.HUGGINGFACE_TTS_API_URL or "https://router.huggingface.co/hf-inference/models").rstrip("/")
    url = f"{base_url}/{model.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "audio/*",
    }
    payload = {"inputs": cleaned}

    response: httpx.Response | None = None
    for attempt in range(2):
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=settings.HUGGINGFACE_TTS_TIMEOUT,
            )
        except httpx.TimeoutException as exc:
            logger.warning("Hugging Face TTS request timed out for model=%s", model)
            raise TTSTimeoutError("Text-to-speech request timed out. Please try again.") from exc
        except httpx.HTTPError as exc:
            logger.warning("Hugging Face TTS transport error for model=%s: %s", model, type(exc).__name__)
            raise TTSUpstreamError("Unable to reach text-to-speech provider.") from exc

        if response.status_code == 503:
            estimated_time = _extract_estimated_time(response)
            if attempt == 0 and 0 < estimated_time <= COLD_START_MAX_RETRY_WAIT_SECONDS:
                logger.info("Hugging Face TTS model=%s warming up; retrying in %.2fs", model, estimated_time)
                time.sleep(estimated_time)
                continue
            raise TTSModelLoadingError("Speech model is warming up. Please try again in a few seconds.")
        break

    assert response is not None
    if response.status_code != 200:
        logger.warning("Hugging Face TTS failed for model=%s with status=%s", model, response.status_code)
        raise TTSUpstreamError("Text-to-speech service returned an error.")

    audio_bytes, media_type = _extract_audio_payload(response, f"Hugging Face TTS model={model}", "audio/flac")
    _store_cached_audio(cache_key, audio_bytes, media_type)
    return audio_bytes, media_type
