from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

# Support invocation both from the repository root and from api/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from huggingface_hub.errors import HfHubHTTPError
from tests.support import BackendTestCase, EXPECTED_ANALYSIS, settings
from app.models import Analysis


def _hf_http_error(status_code: int, json_data: dict | None = None, message: str = "HF error") -> HfHubHTTPError:
    request = httpx.Request("POST", "https://router.huggingface.co/test")
    response = httpx.Response(status_code=status_code, json=json_data, request=request)
    return HfHubHTTPError(message, response=response)


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
        fake_wav = b"RIFF\x24\x00\x00\x00WAVEfmt mock-audio-stream"

        mock_client = MagicMock()
        mock_client.text_to_speech.return_value = fake_wav

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", "hf_secret_test_token"), \
             patch("app.services.tts.InferenceClient", return_value=mock_client) as mock_cls:
            first = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
            second = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertTrue(first.headers["content-type"].startswith("audio/wav"))
        self.assertEqual(first.content, fake_wav)
        self.assertEqual(second.content, fake_wav)
        mock_cls.assert_called_once_with(
            provider=settings.HUGGINGFACE_TTS_PROVIDER,
            api_key="hf_secret_test_token",
            timeout=settings.HUGGINGFACE_TTS_TIMEOUT,
        )
        mock_client.text_to_speech.assert_called_once_with(
            EXPECTED_ANALYSIS["summary"],
            model=settings.HUGGINGFACE_TTS_MODEL,
        )

    def test_tts_detects_audio_mime_types_from_magic_bytes(self) -> None:
        samples = [
            (b"fLaCmock-flac", "audio/flac"),
            (b"ID3\x03\x00mock-mp3", "audio/mpeg"),
            (b"OggSmock-ogg", "audio/ogg"),
        ]
        for index, (payload, expected_mime) in enumerate(samples):
            with self.subTest(expected_mime=expected_mime):
                restaurant = self.restaurant(google_place_id=f"mime-place-{index}", name=f"Mime Cafe {index}")
                row = Analysis(
                    restaurant_id=restaurant["id"],
                    overall_sentiment="POSITIVE",
                    result_json={**EXPECTED_ANALYSIS, "summary": f"Unique summary {index} for {expected_mime}"},
                    review_count=1,
                    model="test-model",
                    created_at=datetime(2025, 1, 1),
                )
                self.db.add(row)
                self.db.commit()

                mock_client = MagicMock()
                mock_client.text_to_speech.return_value = payload
                with patch.object(settings, "HUGGINGFACE_API_TOKEN", "hf_secret_test_token"), \
                     patch("app.services.tts.InferenceClient", return_value=mock_client):
                    res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{row.id}/tts")

                self.assertEqual(res.status_code, 200, res.text)
                self.assertTrue(res.headers["content-type"].startswith(expected_mime))

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

        mock_client = MagicMock()
        mock_client.text_to_speech.return_value = b"fLaCaudio"

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", "hf_secret_test_token"), \
             patch("app.services.tts.InferenceClient", return_value=mock_client):
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

    def test_tts_quota_402_returns_402_without_leaking_token(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))
        secret = "hf_secret_test_token"

        mock_client = MagicMock()
        mock_client.text_to_speech.side_effect = _hf_http_error(
            402,
            json_data={"error": "Purchase pre-paid credits"},
        )

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", secret), \
             patch("app.services.tts.InferenceClient", return_value=mock_client):
            res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(res.status_code, 402)
        self.assertIn("credits", res.json()["detail"].lower())
        self.assertNotIn(secret, res.text)

    def test_tts_cold_start_503_retries_and_handles_loading(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))

        mock_client = MagicMock()
        mock_client.text_to_speech.side_effect = [
            _hf_http_error(503, json_data={"error": "Model is loading", "estimated_time": 1.5}),
            b"fLaCready",
        ]

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", "hf_secret_test_token"), \
             patch("app.services.tts.time.sleep") as mock_sleep, \
             patch("app.services.tts.InferenceClient", return_value=mock_client):
            res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")

        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.content, b"fLaCready")
        self.assertEqual(mock_client.text_to_speech.call_count, 2)
        mock_sleep.assert_called_once_with(1.5)

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

        cold_client = MagicMock()
        cold_client.text_to_speech.side_effect = _hf_http_error(
            503,
            json_data={"error": "Model is loading", "estimated_time": 25.0},
        )
        with patch.object(settings, "HUGGINGFACE_API_TOKEN", "hf_secret_test_token"), \
             patch("app.services.tts.InferenceClient", return_value=cold_client):
            cold_res = self.client.post(f"/restaurants/{other_restaurant['id']}/analyses/{other_analysis.id}/tts")

        self.assertEqual(cold_res.status_code, 503)
        self.assertIn("warming up", cold_res.json()["detail"].lower())

    def test_tts_upstream_error_and_timeout_do_not_leak_token(self) -> None:
        restaurant = self.restaurant()
        analysis = self.analysis_row(restaurant["id"], datetime(2025, 1, 1))
        secret = "hf_secret_test_token"

        with patch.object(settings, "HUGGINGFACE_API_TOKEN", secret):
            timeout_client = MagicMock()
            timeout_client.text_to_speech.side_effect = httpx.ReadTimeout("timeout")
            with patch("app.services.tts.InferenceClient", return_value=timeout_client):
                timeout_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(timeout_res.status_code, 504)
                self.assertNotIn(secret, timeout_res.text)

            upstream_client = MagicMock()
            upstream_client.text_to_speech.side_effect = _hf_http_error(500, message="internal error")
            with patch("app.services.tts.InferenceClient", return_value=upstream_client):
                upstream_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(upstream_res.status_code, 502)
                self.assertNotIn(secret, upstream_res.text)

            empty_client = MagicMock()
            empty_client.text_to_speech.return_value = b""
            with patch("app.services.tts.InferenceClient", return_value=empty_client):
                empty_res = self.client.post(f"/restaurants/{restaurant['id']}/analyses/{analysis.id}/tts")
                self.assertEqual(empty_res.status_code, 502)
                self.assertNotIn(secret, empty_res.text)


if __name__ == "__main__":
    unittest.main()
