import io
from datetime import datetime
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import wave

# Support invocation both from the repository root and from api/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from openai import APITimeoutError, OpenAIError
from tests.support import BackendTestCase, EXPECTED_ANALYSIS, settings
from app.models import Analysis


class _FakeEndpointResponse:
    def __init__(self, status_code: int, content: bytes = b"", headers: dict | None = None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}


def _mock_openai_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 16)

    audio = bytearray(output.getvalue())
    audio[4:8] = b"\xff\xff\xff\xff"
    data_size_offset = audio.index(b"data") + 4
    audio[data_size_offset:data_size_offset + 4] = b"\xff\xff\xff\xff"
    return bytes(audio)


class TestTextToSpeechEndpoint(BackendTestCase):
    def _create_account(self, role: str, email: str, restaurant_ids: list[int] | None = None) -> dict:
        response = self.client.post(
            "/admin/users",
            json={
                "email": email,
                "full_name": role.title(),
                "password": "secure-test-password-123",
                "role": role,
                "restaurant_ids": restaurant_ids or [],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _login_as(self, email: str) -> None:
        response = self.client.post("/auth/login", json={"email": email, "password": "secure-test-password-123"})
        self.assertEqual(response.status_code, 200, response.text)
        self.client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})

    def test_tts_synthesizes_summary_and_caches_audio(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))
        fake_audio = _mock_openai_wav()
        expected_audio = bytearray(fake_audio)
        expected_audio[4:8] = (len(fake_audio) - 8).to_bytes(4, "little")
        data_size_offset = expected_audio.index(b"data") + 4
        expected_audio[data_size_offset:data_size_offset + 4] = (
            len(fake_audio) - data_size_offset - 4
        ).to_bytes(4, "little")

        with patch.object(settings, "OPENAI_API_KEY", "test-openai-key"), \
             patch("app.services.tts.OpenAI") as mock_openai:
            speech_create = mock_openai.return_value.audio.speech.create
            speech_create.return_value = SimpleNamespace(content=fake_audio)
            first = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
            second = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertTrue(first.headers["content-type"].startswith("audio/wav"))
        self.assertEqual(first.content, bytes(expected_audio))
        self.assertEqual(second.content, bytes(expected_audio))
        with wave.open(io.BytesIO(first.content), "rb") as wav:
            self.assertEqual(wav.getnframes(), 16)
        self.assertEqual(speech_create.call_count, 1)
        self.assertEqual(
            speech_create.call_args.kwargs,
            {
                "model": settings.OPENAI_TTS_MODEL,
                "voice": settings.OPENAI_TTS_VOICE,
                "input": EXPECTED_ANALYSIS["summary"],
                "response_format": "wav",
            },
        )
        mock_openai.assert_called_once_with(
            api_key="test-openai-key",
            timeout=settings.OPENAI_TTS_TIMEOUT,
        )

    def test_tts_voice_is_part_of_cache_key(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))

        with patch.object(settings, "OPENAI_API_KEY", "test-openai-key"), \
             patch("app.services.tts.OpenAI") as mock_openai:
            mock_openai.return_value.audio.speech.create.return_value = SimpleNamespace(content=_mock_openai_wav())
            first = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
            with patch.object(settings, "OPENAI_TTS_VOICE", "alloy"):
                second = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(mock_openai.return_value.audio.speech.create.call_count, 2)

    def test_tts_rbac_enforcement(self) -> None:
        assigned = self.restaurant()
        unassigned = self.restaurant(google_place_id="other-place", name="Other Cafe")
        assigned_analysis = self.analysis_row(assigned["id"], datetime(2025, 1, 1))
        unassigned_analysis = self.analysis_row(unassigned["id"], datetime(2025, 1, 1))

        self._create_account("OWNER", "tts-owner@example.com", [assigned["id"]])
        self._create_account("ANALYST", "tts-analyst@example.com")

        admin_auth = self.client.headers["Authorization"]
        self.client.headers.pop("Authorization")
        self.assertEqual(
            self.client.post(f"/restaurants/{assigned['id']}/analyses/{assigned_analysis.id}/tts").status_code,
            401,
        )

        with patch.object(settings, "OPENAI_API_KEY", "test-openai-key"), \
             patch("app.services.tts.OpenAI") as mock_openai:
            mock_openai.return_value.audio.speech.create.return_value = SimpleNamespace(content=_mock_openai_wav())
            self._login_as("tts-owner@example.com")
            self.assertEqual(
                self.client.post(f"/restaurants/{assigned['id']}/analyses/{assigned_analysis.id}/tts").status_code,
                200,
            )
            self.assertEqual(
                self.client.post(f"/restaurants/{unassigned['id']}/analyses/{unassigned_analysis.id}/tts").status_code,
                404,
            )

            self._login_as("tts-analyst@example.com")
            self.assertEqual(
                self.client.post(f"/restaurants/{unassigned['id']}/analyses/{unassigned_analysis.id}/tts").status_code,
                200,
            )

            self.client.headers.update({"Authorization": admin_auth})
            self.assertEqual(
                self.client.post(f"/restaurants/{unassigned['id']}/analyses/{unassigned_analysis.id}/tts").status_code,
                200,
            )

    def test_tts_not_found_and_mismatched_analysis(self) -> None:
        first = self.restaurant()
        second = self.restaurant(google_place_id="second-place", name="Second Bistro")
        analysis_second = self.analysis_row(second["id"], datetime(2025, 1, 1))

        self.assertEqual(self.client.post("/restaurants/99999/analyses/1/tts").status_code, 404)
        self.assertEqual(self.client.post(f"/restaurants/{first['id']}/analyses/99999/tts").status_code, 404)
        self.assertEqual(
            self.client.post(f"/restaurants/{first['id']}/analyses/{analysis_second.id}/tts").status_code,
            404,
        )

    def test_tts_empty_summary_returns_400(self) -> None:
        restaurant = self.restaurant()
        empty_analysis = Analysis(
            restaurant_id=restaurant["id"],
            overall_sentiment="NEUTRAL",
            result_json={**EXPECTED_ANALYSIS, "summary": "   "},
            review_count=0,
            model="test-model",
            created_at=datetime(2025, 1, 1),
        )
        self.db.add(empty_analysis)
        self.db.commit()

        response = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{empty_analysis.id}/tts")
        self.assertEqual(response.status_code, 400)

    def test_tts_unconfigured_api_key_returns_503(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))

        with patch.object(settings, "OPENAI_API_KEY", ""):
            response = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["detail"].lower())

    def test_tts_rejects_non_wav_openai_response(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))

        with patch.object(settings, "OPENAI_API_KEY", "test-openai-key"), \
             patch("app.services.tts.OpenAI") as mock_openai:
            mock_openai.return_value.audio.speech.create.return_value = SimpleNamespace(content=b"not-a-wav")
            response = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(response.status_code, 502)
        self.assertIn("invalid WAV", response.json()["detail"])

    def test_tts_timeout_and_upstream_errors_do_not_leak_api_key(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))
        api_key = "test-openai-secret"
        request = httpx.Request("POST", "https://api.openai.com/v1/audio/speech")

        with patch.object(settings, "OPENAI_API_KEY", api_key), \
             patch("app.services.tts.OpenAI") as mock_openai:
            speech_create = mock_openai.return_value.audio.speech.create
            speech_create.side_effect = [
                APITimeoutError(request=request),
                OpenAIError("upstream failure"),
            ]

            timeout_response = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
            self.assertEqual(timeout_response.status_code, 504)
            self.assertNotIn(api_key, timeout_response.text)

            upstream_response = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
            self.assertEqual(upstream_response.status_code, 502)
            self.assertNotIn(api_key, upstream_response.text)

    def test_tts_custom_base_url_calls_openai_speech_endpoint_and_caches(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))
        fake_mp3 = b"ID3\x04\x00mock-kokoro-mp3"

        with patch.object(settings, "TTS_PROVIDER", "kokoro"), \
             patch.object(settings, "TTS_BASE_URL", "https://tts.example.trycloudflare.com/"), \
             patch("app.services.tts.httpx.post", return_value=_FakeEndpointResponse(
                 200,
                 content=fake_mp3,
                 headers={"content-type": "audio/mpeg"},
             )) as mock_post:
            first = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
            second = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertTrue(first.headers["content-type"].startswith("audio/mpeg"))
        self.assertEqual(first.content, fake_mp3)
        self.assertEqual(second.content, fake_mp3)
        self.assertEqual(mock_post.call_count, 1)

        called_url = mock_post.call_args.args[0]
        called_kwargs = mock_post.call_args.kwargs
        self.assertEqual(called_url, "https://tts.example.trycloudflare.com/v1/audio/speech")
        self.assertEqual(
            called_kwargs["json"],
            {
                "model": settings.TTS_MODEL,
                "input": EXPECTED_ANALYSIS["summary"],
                "voice": settings.TTS_VOICE,
                "response_format": "mp3",
            },
        )

    def test_tts_custom_base_url_errors_and_timeout(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))

        with patch.object(settings, "TTS_PROVIDER", "kokoro"), \
             patch.object(settings, "TTS_BASE_URL", "http://localhost:8880"):
            with patch("app.services.tts.httpx.post", side_effect=httpx.ReadTimeout("timeout")):
                timeout_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(timeout_res.status_code, 504)

            with patch("app.services.tts.httpx.post", return_value=_FakeEndpointResponse(500, content=b"internal error")):
                upstream_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(upstream_res.status_code, 502)

            with patch("app.services.tts.httpx.post", return_value=_FakeEndpointResponse(
                200,
                content=b'{"error":"bad payload"}',
                headers={"content-type": "application/json"},
            )):
                json_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(json_res.status_code, 502)


if __name__ == "__main__":
    unittest.main()
