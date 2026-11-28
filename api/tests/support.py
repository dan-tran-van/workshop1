"""Isolated fixtures and network guards; application behavior is unchanged."""

from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

# Set test configuration BEFORE importing the app. Never read developer keys.
with patch.dict(os.environ, {
    "DATABASE_URL": "sqlite://", "OPENAI_API_KEY": "", "GOOGLE_PLACES_API_KEY": "",
    "HUGGINGFACE_API_TOKEN": "",
    "CORS_ORIGINS": '["http://localhost:5173"]',
}):
    from app.main import app

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.database import Base, get_db
from app.models import Analysis, Restaurant, User
from app.services.auth import create_access_token, hash_password
from app.services.tts import clear_tts_cache

EXPECTED_ANALYSIS = {
    "overall_sentiment": "MIXED",
    "summary": "Guests enjoy the food but report slow service.",
    "estimated_rating_trend": "STABLE",
    "aspect_breakdown": [
        {"aspect": "food", "sentiment": "POSITIVE", "score": 5.0,
         "summary": "Delicious food.", "highlights": ["Great food"]},
        {"aspect": "service", "sentiment": "NEGATIVE", "score": 2.0,
         "summary": "Slow service.", "highlights": ["Long wait"]},
    ],
    "prioritized_improvements": [
        {"priority": "HIGH", "aspect": "service", "issue": "Long waits",
         "recommended_action": "Add a server at peak hours.", "expected_impact": "Shorter waits"},
    ],
    "strengths_to_keep": [
        {"aspect": "food", "strength": "Fresh dishes", "marketing_tip": "Show the seasonal menu."},
    ],
}


class BackendTestCase(unittest.TestCase):
    """Every test owns a temporary SQLite file and request-scoped DB sessions."""

    def setUp(self) -> None:
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        folder = self.resources.enter_context(TemporaryDirectory(prefix="restaurant-tests-"))
        self.database_path = Path(folder) / "test.sqlite"
        self.engine = create_engine(f"sqlite:///{self.database_path.as_posix()}", connect_args={"check_same_thread": False})
        self.resources.callback(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False)
        self.db = self.resources.enter_context(self.session_factory())

        def override_db():
            with self.session_factory() as session:
                yield session

        previous = app.dependency_overrides.copy()
        self.resources.callback(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(previous)))
        app.dependency_overrides[get_db] = override_db
        self.resources.enter_context(patch("app.main.engine", self.engine))
        self.resources.enter_context(patch.object(settings, "OPENAI_API_KEY", ""))
        self.resources.enter_context(patch.object(settings, "GOOGLE_PLACES_API_KEY", ""))
        self.resources.enter_context(patch.object(settings, "HUGGINGFACE_API_TOKEN", ""))
        clear_tts_cache()
        self.unmocked_requests: list[str] = []

        def deny_provider(*args, **kwargs):
            self.unmocked_requests.append("unmocked provider call")
            raise AssertionError("External providers must be mocked in tests")

        self.openai_guard = self.resources.enter_context(patch("openai.OpenAI", side_effect=deny_provider))
        self.google_guard = self.resources.enter_context(patch("app.services.sync.httpx.get", side_effect=deny_provider))
        self.hf_guard = self.resources.enter_context(patch("app.services.tts.InferenceClient", side_effect=deny_provider))
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        original_create_connection = socket.create_connection
        original_getaddrinfo = socket.getaddrinfo

        def check_address(address) -> None:
            # Loopback is needed for Windows event-loop plumbing. TestClient uses ASGI.
            if isinstance(address, tuple) and address[0] not in {"localhost", "127.0.0.1", "::1"}:
                self.unmocked_requests.append("external socket connection")
                raise AssertionError("External network connections are disabled in tests")

        def guarded_connect(sock, address):
            check_address(address)
            return original_connect(sock, address)

        def guarded_connect_ex(sock, address):
            check_address(address)
            return original_connect_ex(sock, address)

        def guarded_create_connection(address, *args, **kwargs):
            check_address(address)
            return original_create_connection(address, *args, **kwargs)

        def guarded_getaddrinfo(host, port, *args, **kwargs):
            check_address((host, port))
            return original_getaddrinfo(host, port, *args, **kwargs)

        self.resources.enter_context(patch("socket.socket.connect", guarded_connect))
        self.resources.enter_context(patch("socket.socket.connect_ex", guarded_connect_ex))
        self.resources.enter_context(patch("socket.create_connection", guarded_create_connection))
        self.resources.enter_context(patch("socket.getaddrinfo", guarded_getaddrinfo))
        self.client = self.resources.enter_context(TestClient(app, raise_server_exceptions=False))
        admin = User(
            email="admin@example.com",
            full_name="Test Administrator",
            password_hash=hash_password("test-admin-password-123"),
            role="ADMIN",
            is_active=True,
        )
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)
        self.client.headers.update({"Authorization": f"Bearer {create_access_token(admin)}"})
        self.assertEqual(self.db.query(Restaurant).count(), 0)

    def tearDown(self) -> None:
        self.assertEqual(self.unmocked_requests, [], "A real external request was attempted")

    def restaurant(self, **overrides) -> dict:
        payload = {"google_place_id": "test-place", "name": "Cedar Kitchen",
                   "address": "25 Market Street", "google_rating": 4.0, "user_rating_count": 0}
        payload.update(overrides)
        response = self.client.post("/restaurants", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def review_payload(self, restaurant_id: int, **overrides) -> dict:
        payload = {"restaurant_id": restaurant_id, "author_name": "Test Guest", "rating": 4.0,
                   "text": "Fresh food and friendly service", "published_at": "2020-01-02T12:00:00Z"}
        payload.update(overrides)
        return payload

    def review(self, restaurant_id: int, **overrides) -> dict:
        response = self.client.post(f"/restaurants/{restaurant_id}/reviews", json=self.review_payload(restaurant_id, **overrides))
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def target(self, **overrides) -> dict:
        payload = {"target_type": "place_id", "value": "test-google-place", "language_code": "en", "is_active": True}
        payload.update(overrides)
        response = self.client.post("/sync/targets", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def analysis_row(self, restaurant_id: int, created_at: datetime) -> Analysis:
        row = Analysis(restaurant_id=restaurant_id, overall_sentiment="MIXED", result_json=deepcopy(EXPECTED_ANALYSIS),
                       review_count=0, model="test-model", created_at=created_at)
        self.db.add(row)
        self.db.commit()
        return row

    @contextmanager
    def openai_response(self, content=None):
        """Exercise the real analysis service with a fake SDK response."""
        if content is None:
            content = json.dumps(EXPECTED_ANALYSIS)
        with patch.object(settings, "OPENAI_API_KEY", "test-only-not-a-real-key"), patch("openai.OpenAI") as constructor:
            completion = constructor.return_value.chat.completions.create
            completion.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
            yield completion
