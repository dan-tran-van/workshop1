from collections import OrderedDict
import hashlib
import logging
import threading
import time
from typing import Any, Tuple

import httpx
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

from app.config import settings

logger = logging.getLogger(__name__)

MAX_TTS_TEXT_LENGTH = 2000
TTS_CACHE_MAX_ITEMS = 64
COLD_START_MAX_RETRY_WAIT_SECONDS = 5.0

_tts_cache_lock = threading.Lock()
_tts_cache: "OrderedDict[tuple[str, str, str], tuple[bytes, str]]" = OrderedDict()


class TTSError(Exception):
    """Base error for Text-to-Speech synthesis failures."""


class TTSNotConfiguredError(TTSError):
    """Raised when the Hugging Face API token is missing."""


class TTSQuotaError(TTSError):
    """Raised when Hugging Face Inference Provider credits are exhausted."""


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


def _extract_estimated_time(response: Any) -> float:
    if response is None:
        return 0.0
    try:
        payload = response.json()
        if isinstance(payload, dict):
            estimated = payload.get("estimated_time")
            if isinstance(estimated, (int, float)):
                return float(estimated)
    except Exception:
        pass
    return 0.0


def _detect_audio_media_type(audio_bytes: bytes) -> str:
    if audio_bytes.startswith(b"RIFF") and audio_bytes[8:12] == b"WAVE":
        return "audio/wav"
    if audio_bytes.startswith(b"fLaC"):
        return "audio/flac"
    if audio_bytes.startswith(b"OggS"):
        return "audio/ogg"
    if audio_bytes.startswith(b"ID3") or (
        len(audio_bytes) >= 2 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0
    ):
        return "audio/mpeg"
    return "audio/mpeg"


def synthesize_speech(text: str) -> Tuple[bytes, str]:
    """
    Convert analysis summary text to speech bytes using Hugging Face InferenceClient.
    Caches synthesized audio in a bounded thread-safe LRU cache keyed by (provider, model, text hash).
    """
    cleaned = _normalize_tts_text(text)

    token = (settings.HUGGINGFACE_API_TOKEN or "").strip()
    if not token:
        raise TTSNotConfiguredError("Text-to-speech is not configured on the server.")

    provider = (settings.HUGGINGFACE_TTS_PROVIDER or "auto").strip() or "auto"
    model = (settings.HUGGINGFACE_TTS_MODEL or "hexgrad/Kokoro-82M").strip() or "hexgrad/Kokoro-82M"
    text_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    cache_key = (provider, model, text_hash)

    with _tts_cache_lock:
        cached = _tts_cache.get(cache_key)
        if cached is not None:
            _tts_cache.move_to_end(cache_key)
            return cached

    client = InferenceClient(
        provider=provider,
        api_key=token,
        timeout=settings.HUGGINGFACE_TTS_TIMEOUT,
    )

    audio_result: Any = None
    for attempt in range(2):
        try:
            audio_result = client.text_to_speech(cleaned, model=model)
            break
        except (httpx.TimeoutException, TimeoutError) as exc:
            logger.warning("Hugging Face TTS request timed out for model=%s provider=%s", model, provider)
            raise TTSTimeoutError("Text-to-speech request timed out. Please try again.") from exc
        except HfHubHTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 402:
                logger.warning("Hugging Face TTS credits exhausted for model=%s provider=%s", model, provider)
                raise TTSQuotaError(
                    "Hugging Face Inference Provider credits are exhausted. "
                    "Please check your Hugging Face billing or PRO subscription."
                ) from exc
            if status_code == 503:
                estimated_time = _extract_estimated_time(exc.response)
                if attempt == 0 and 0 < estimated_time <= COLD_START_MAX_RETRY_WAIT_SECONDS:
                    logger.info(
                        "Hugging Face TTS model=%s provider=%s warming up; retrying in %.2fs",
                        model,
                        provider,
                        estimated_time,
                    )
                    time.sleep(estimated_time)
                    continue
                raise TTSModelLoadingError("Speech model is warming up. Please try again in a few seconds.") from exc
            if status_code in (401, 403):
                logger.warning(
                    "Hugging Face TTS authorization failed for model=%s provider=%s status=%s",
                    model,
                    provider,
                    status_code,
                )
                raise TTSUpstreamError(
                    "Hugging Face API token is invalid or lacks Inference Providers permission."
                ) from exc
            logger.warning(
                "Hugging Face TTS failed for model=%s provider=%s with status=%s",
                model,
                provider,
                status_code,
            )
            raise TTSUpstreamError("Text-to-speech service returned an error.") from exc
        except Exception as exc:
            logger.warning(
                "Hugging Face TTS error for model=%s provider=%s: %s",
                model,
                provider,
                type(exc).__name__,
            )
            raise TTSUpstreamError("Unable to reach text-to-speech provider.") from exc

    if not isinstance(audio_result, (bytes, bytearray)) or not audio_result:
        logger.warning("Hugging Face TTS returned empty or invalid audio for model=%s provider=%s", model, provider)
        raise TTSUpstreamError("Unexpected response format from text-to-speech provider.")

    audio_bytes = bytes(audio_result)
    media_type = _detect_audio_media_type(audio_bytes)

    with _tts_cache_lock:
        _tts_cache[cache_key] = (audio_bytes, media_type)
        _tts_cache.move_to_end(cache_key)
        while len(_tts_cache) > TTS_CACHE_MAX_ITEMS:
            _tts_cache.popitem(last=False)

    return audio_bytes, media_type
