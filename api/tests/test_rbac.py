import unittest
from pathlib import Path
import sys
from unittest.mock import patch

# Support invocation both from the repository root and from api/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import BackendTestCase, settings
from app.models import User


class TestRoleBasedAccessControl(BackendTestCase):
    def create_account(self, role: str, email: str, restaurant_ids: list[int] | None = None) -> dict:
        response = self.client.post("/admin/users", json={
            "email": email,
            "full_name": role.title(),
            "password": "secure-test-password-123",
            "role": role,
            "restaurant_ids": restaurant_ids or [],
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def login_as(self, email: str) -> None:
        response = self.client.post("/auth/login", json={"email": email, "password": "secure-test-password-123"})
        self.assertEqual(response.status_code, 200, response.text)
        self.client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})

    def test_authentication_required_for_restaurant_and_sync_endpoints(self) -> None:
        self.client.headers.pop("Authorization")
        self.assertEqual(self.client.get("/restaurants").status_code, 401)
        self.assertEqual(self.client.get("/auth/me/analysis-history").status_code, 401)
        self.assertEqual(self.client.get("/sync/targets").status_code, 401)
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_analysis_history_is_per_user_and_records_cached_requests(self) -> None:
        restaurant = self.restaurant()
        self.create_account("ANALYST", "history-analyst@example.com")

        first = self.client.post(f"/restaurants/{restaurant['id']}/analyze", json={})
        second = self.client.post(f"/restaurants/{restaurant['id']}/analyze", json={})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        refreshed = self.client.post(
            f"/restaurants/{restaurant['id']}/analyze",
            json={"force_refresh": True},
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertNotEqual(refreshed.json()["id"], first.json()["id"])

        admin_history = self.client.get("/auth/me/analysis-history")
        self.assertEqual(admin_history.status_code, 200, admin_history.text)
        self.assertEqual([run["analysis"]["id"] for run in admin_history.json()],
                         [refreshed.json()["id"], first.json()["id"], first.json()["id"]])

        self.login_as("history-analyst@example.com")
        self.assertEqual(self.client.get("/auth/me/analysis-history").json(), [])
        cached = self.client.post(f"/restaurants/{restaurant['id']}/analyze", json={})
        self.assertEqual(cached.status_code, 200, cached.text)
        self.assertIn(cached.json()["id"], {first.json()["id"], refreshed.json()["id"]})
        analyst_history = self.client.get("/auth/me/analysis-history")
        self.assertEqual(analyst_history.status_code, 200, analyst_history.text)
        self.assertEqual(len(analyst_history.json()), 1)
        self.assertEqual(analyst_history.json()[0]["analysis"]["id"], cached.json()["id"])

    def test_owner_history_hides_restaurants_after_assignment_is_removed(self) -> None:
        restaurant = self.restaurant()
        owner = self.create_account("OWNER", "history-owner@example.com", [restaurant["id"]])
        admin_authorization = self.client.headers["Authorization"]
        self.login_as("history-owner@example.com")
        analysis = self.client.post(f"/restaurants/{restaurant['id']}/analyze", json={})
        self.assertEqual(analysis.status_code, 200, analysis.text)
        self.assertEqual(len(self.client.get("/auth/me/analysis-history").json()), 1)

        self.client.headers.update({"Authorization": admin_authorization})
        updated = self.client.patch(f"/admin/users/{owner['id']}", json={"restaurant_ids": []})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.login_as("history-owner@example.com")
        self.assertEqual(self.client.get("/auth/me/analysis-history").json(), [])

    def test_analyst_can_read_and_analyze_but_cannot_manage_or_sync(self) -> None:
        restaurant = self.restaurant()
        self.create_account("ANALYST", "analyst@example.com")
        self.login_as("analyst@example.com")

        self.assertEqual(self.client.get("/restaurants").status_code, 200)
        self.assertEqual(self.client.post(f"/restaurants/{restaurant['id']}/analyze", json={}).status_code, 200)
        self.assertEqual(self.client.post("/restaurants", json={
            "google_place_id": "analyst-place",
            "name": "Analyst Cafe",
        }).status_code, 403)
        self.assertEqual(self.client.get("/admin/users").status_code, 403)
        self.assertEqual(self.client.get("/sync/targets").status_code, 403)

    def test_owner_is_limited_to_assigned_restaurants_and_can_add_own(self) -> None:
        assigned = self.restaurant()
        unassigned = self.restaurant(google_place_id="other-place", name="Other Cafe")
        owner = self.create_account("OWNER", "owner@example.com", [assigned["id"]])
        self.login_as("owner@example.com")

        self.assertEqual([item["id"] for item in self.client.get("/restaurants").json()], [assigned["id"]])
        self.assertEqual(self.client.get(f"/restaurants/{unassigned['id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/restaurants/{assigned['id']}/reviews").status_code, 200)

        created = self.client.post("/restaurants", json={
            "google_place_id": "owners-place",
            "name": "Owner Cafe",
        })
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["id"], self.client.get("/restaurants").json()[1]["id"])
        stored_owner = self.db.get(User, owner["id"])
        self.assertEqual({item.id for item in stored_owner.restaurants}, {assigned["id"], created.json()["id"]})
        self.assertEqual(self.client.post(f"/restaurants/{unassigned['id']}/analyze", json={}).status_code, 404)
        self.assertEqual(self.client.post(f"/restaurants/{assigned['id']}/reviews", json={
            "author_name": "Guest",
            "rating": 4,
            "text": "Good meal",
            "published_at": "2025-01-01T00:00:00Z",
        }).status_code, 403)

    def test_admin_can_create_users_but_cannot_disable_themselves(self) -> None:
        created = self.create_account("OWNER", "new-owner@example.com")
        self.assertEqual(created["role"], "OWNER")
        self.assertEqual(self.client.get("/admin/users").status_code, 200)
        response = self.client.patch(f"/admin/users/{self.client.get('/auth/me').json()['id']}", json={"is_active": False})
        self.assertEqual(response.status_code, 409)

    def test_login_rejects_bad_credentials_and_disabled_users(self) -> None:
        self.assertEqual(self.client.post("/auth/login", json={
            "email": "admin@example.com",
            "password": "wrong-password",
        }).status_code, 401)
        account = self.create_account("ANALYST", "disabled@example.com")
        self.db.get(User, account["id"]).is_active = False
        self.db.commit()
        self.assertEqual(self.client.post("/auth/login", json={
            "email": "disabled@example.com",
            "password": "secure-test-password-123",
        }).status_code, 401)

    def test_first_admin_requires_setup_key_and_can_only_be_created_once(self) -> None:
        self.db.query(User).delete()
        self.db.commit()
        self.assertTrue(self.client.get("/auth/setup").json()["setup_required"])

        payload = {
            "email": "first-admin@example.com",
            "full_name": "First Admin",
            "password": "secure-test-password-123",
            "setup_key": "one-time-setup-key",
        }
        with patch.object(settings, "AUTH_BOOTSTRAP_KEY", "one-time-setup-key"):
            invalid = {**payload, "setup_key": "wrong-key"}
            self.assertEqual(self.client.post("/auth/bootstrap", json=invalid).status_code, 403)
            created = self.client.post("/auth/bootstrap", json=payload)
            self.assertEqual(created.status_code, 201, created.text)
            self.assertEqual(created.json()["user"]["role"], "ADMIN")
            self.assertFalse(self.client.get("/auth/setup").json()["setup_required"])
            self.assertEqual(self.client.post("/auth/bootstrap", json=payload).status_code, 409)


if __name__ == "__main__":
    unittest.main()
