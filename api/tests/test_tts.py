from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# Support invocation both from the repository root and from api/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from tests.support import BackendTestCase, EXPECTED_ANALYSIS, settings
from app.models import Analysis


class _FakeHFResponse:
    def __init__(self, status_code: int, content: bytes = b"", headers: dict | None = None, json_data: dict | None = None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self._json_data = json_data

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON payload")
        return self._json_data


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
        fake_audio = b"fLaCmock-audio-stream"

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", "hf_secret_test_token"), \
             patch("app.services.tts.httpx.post", return_value=_FakeHFResponse(
                 200,
                 content=fake_audio,
                 headers={"content-type": "audio/flac"},
             )) as mock_post:
            first = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
            second = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertTrue(first.headers["content-type"].startswith("audio/flac"))
        self.assertEqual(first.content, fake_audio)
        self.assertEqual(second.content, fake_audio)
        self.assertEqual(mock_post.call_count, 1)

        called_url = mock_post.call_args.args[0]
        called_kwargs = mock_post.call_args.kwargs
        self.assertIn(settings.HUGGINGFACE_TTS_MODEL, called_url)
        self.assertEqual(called_kwargs["headers"]["Authorization"], "Bearer hf_secret_test_token")
        self.assertEqual(called_kwargs["json"], {"inputs": EXPECTED_ANALYSIS["summary"]})

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

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", "hf_secret_test_token"), \
             patch("app.services.tts.httpx.post", return_value=_FakeHFResponse(
                 200,
                 content=b"fLaCaudio",
                 headers={"content-type": "audio/flac"},
             )):
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

    def test_tts_unconfigured_token_returns_503(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", ""):
            response = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["detail"].lower())

    def test_tts_cold_start_503_retries_and_handles_loading(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", "hf_secret_test_token"), \
             patch("app.services.tts.time.sleep") as mock_sleep, \
             patch("app.services.tts.httpx.post", side_effect=[
                 _FakeHFResponse(503, json_data={"error": "Model is loading", "estimated_time": 1.5}),
                 _FakeHFResponse(200, content=b"fLaCready", headers={"content-type": "audio/flac"}),
             ]) as mock_post:
            res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.content, b"fLaCready")
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(1.5)

        # Now test long cold start (> 5s) without retrying
        other_restaurant = self.restaurant(google_place_id="cold-place", name="Cold Cafe")
        other_analysis = Analysis(
            restaurant_id=other_restaurant["id"],
            overall_sentiment="MIXED",
            result_json={**EXPECTED_ANALYSIS, "summary": "Unique summary for long cold start test."},
            review_count=1,
            model="test-model",
            created_at=datetime(2025, 1, 2),
        )
        self.db.add(other_analysis)
        self.db.commit()

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", "hf_secret_test_token"), \
             patch("app.services.tts.httpx.post", return_value=_FakeHFResponse(
                 503,
                 json_data={"error": "Model is loading", "estimated_time": 25.0},
             )):
            cold_res = self.client.post(f"/restaurants/{other_restaurant['id']}/analyses/{other_analysis.id}/tts")

        self.assertEqual(cold_res.status_code, 503)
        self.assertIn("warming up", cold_res.json()["detail"].lower())

    def test_tts_upstream_error_and_timeout_do_not_leak_token(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))
        secret = "hf_secret_test_token"

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", secret):
            with patch("app.services.tts.httpx.post", side_effect=httpx.ReadTimeout("timeout")):
                timeout_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(timeout_res.status_code, 504)
                self.assertNotIn(secret, timeout_res.text)

            with patch("app.services.tts.httpx.post", return_value=_FakeHFResponse(500, content=b"internal error")):
                upstream_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(upstream_res.status_code, 502)
                self.assertNotIn(secret, upstream_res.text)

            with patch("app.services.tts.httpx.post", return_value=_FakeHFResponse(
                200,
                content=b'{"error":"bad payload"}',
                headers={"content-type": "application/json"},
            )):
                json_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(json_res.status_code, 502)
                self.assertNotIn(secret, json_res.text)

    def test_tts_custom_base_url_calls_openai_speech_endpoint_and_caches(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))
        fake_mp3 = b"ID3\x04\x00mock-kokoro-mp3"

        with patch.object(settings, "TTS_BASE_URL", "https://tts.example.trycloudflare.com/"), \
             patch.object(settings, "HUGGINGFACE_API_TOKEN", ""), \
             patch("app.services.tts.httpx.post", return_value=_FakeHFResponse(
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

        with patch.object(settings, "TTS_BASE_URL", "http://localhost:8880"):
            with patch("app.services.tts.httpx.post", side_effect=httpx.ReadTimeout("timeout")):
                timeout_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(timeout_res.status_code, 504)

            with patch("app.services.tts.httpx.post", return_value=_FakeHFResponse(500, content=b"internal error")):
                upstream_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(upstream_res.status_code, 502)

            with patch("app.services.tts.httpx.post", return_value=_FakeHFResponse(
                200,
                content=b'{"error":"bad payload"}',
                headers={"content-type": "application/json"},
            )):
                json_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(json_res.status_code, 502)


if __name__ == "__main__":
    unittest.main()
