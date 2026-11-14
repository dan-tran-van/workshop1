import unittest
import os
import sys

# Ensure api directory is in Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestRestaurantReviewInsightsAPI(unittest.TestCase):
    def test_root_and_health(self):
        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "online")

        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

    def test_list_and_search_restaurants(self):
        res = client.get("/restaurants")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(len(data), 2)
        self.assertTrue(any("Golden Lotus" in r["name"] for r in data))

        # Test search filter
        search_res = client.get("/restaurants?q=Sakura")
        self.assertEqual(search_res.status_code, 200)
        search_data = search_res.json()
        self.assertEqual(len(search_data), 1)
        self.assertIn("Sakura", search_data[0]["name"])

    def test_get_restaurant_detail(self):
        list_res = client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        detail_res = client.get(f"/restaurants/{first_id}")
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertIn("reviews", detail)
        self.assertIn("latest_analysis", detail)
        self.assertGreater(len(detail["reviews"]), 0)

    def test_trigger_analysis(self):
        list_res = client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        analysis_res = client.post(
            f"/restaurants/{first_id}/analyze",
            json={"force_refresh": True}
        )
        self.assertEqual(analysis_res.status_code, 200)
        analysis = analysis_res.json()
        self.assertIn("overall_sentiment", analysis)
        self.assertIn("result_json", analysis)
        self.assertIn("aspect_breakdown", analysis["result_json"])
        self.assertIn("prioritized_improvements", analysis["result_json"])

    def test_sync_endpoints(self):
        targets_res = client.get("/sync/targets")
        self.assertEqual(targets_res.status_code, 200)
        self.assertGreaterEqual(len(targets_res.json()), 1)

        run_res = client.post("/sync/run")
        self.assertEqual(run_res.status_code, 200)
        run_data = run_res.json()
        self.assertEqual(run_data["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
