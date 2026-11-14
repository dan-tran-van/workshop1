import unittest
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Ensure api directory is in Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.support import BackendTestCase
from app.models import Restaurant, Review, Analysis, SyncTarget, SyncRun
from app.services.analysis import generate_mock_analysis, get_or_run_restaurant_analysis
from app.services.sync import fetch_from_google_places

class SeededIntegrationTestCase(BackendTestCase):
    """Own all data used by the integration tests; never require a seed database."""

    def setUp(self):
        super().setUp()
        restaurant = self.restaurant()
        self.review(restaurant["id"])
        self.target()



class TestRestaurantReviewInsightsAPI(SeededIntegrationTestCase):
    """End-to-end smoke integration tests for core workflows."""

    def test_root_and_health(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "online")

        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

    def test_list_and_search_restaurants(self):
        res = self.client.get("/restaurants")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(len(data), 1)

        # Test search filter with partial term from first restaurant
        first_name = data[0]["name"]
        query_word = first_name.split()[0]
        search_res = self.client.get(f"/restaurants?q={query_word}")
        self.assertEqual(search_res.status_code, 200)
        search_data = search_res.json()
        self.assertGreaterEqual(len(search_data), 1)
        self.assertTrue(any(query_word.lower() in r["name"].lower() or query_word.lower() in (r.get("address") or "").lower() for r in search_data))

    def test_get_restaurant_detail(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        detail_res = self.client.get(f"/restaurants/{first_id}")
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertIn("reviews", detail)
        self.assertIn("latest_analysis", detail)
        self.assertIn("review_count", detail)

    def test_trigger_analysis(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        with patch("app.services.analysis.settings.OPENAI_API_KEY", ""):
            analysis_res = self.client.post(
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
        targets_res = self.client.get("/sync/targets")
        self.assertEqual(targets_res.status_code, 200)
        self.assertGreaterEqual(len(targets_res.json()), 1)

        run_res = self.client.post("/sync/run")
        self.assertEqual(run_res.status_code, 200)
        run_data = run_res.json()
        self.assertEqual(run_data["status"], "COMPLETED")


class TestHealthAndRootAPI(SeededIntegrationTestCase):
    """Granular tests for root application info and health check."""

    def test_root_endpoint_metadata(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("app", data)
        self.assertEqual(data["docs_url"], "/docs")

    def test_health_check_endpoint(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})


class TestRestaurantsAPI(SeededIntegrationTestCase):
    """Tests for Restaurant CRUD, search filters, pagination bounds, and validation."""

    def _delete_restaurant(self, restaurant_id: int):
        with self.session_factory() as db:
            db.query(Restaurant).filter(Restaurant.id == restaurant_id).delete()
            db.commit()

    def test_list_restaurants_structure(self):
        res = self.client.get("/restaurants")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

        first = data[0]
        for field in ["id", "name", "google_place_id", "review_count", "google_rating", "address"]:
            self.assertIn(field, first)

    def test_search_restaurants_by_address(self):
        list_res = self.client.get("/restaurants")
        restaurants_with_addr = [r for r in list_res.json() if r.get("address")]
        self.assertTrue(restaurants_with_addr)
        if restaurants_with_addr:
            import re
            addr = restaurants_with_addr[0]["address"]
            tokens = [t for t in re.findall(r"\b[A-Za-z]{4,}\b", addr) if t.lower() != "city"]
            target_addr_word = tokens[0] if tokens else "Vietnam"
            search_res = self.client.get(f"/restaurants?q={target_addr_word}")
            self.assertEqual(search_res.status_code, 200)
            self.assertGreaterEqual(len(search_res.json()), 1)

    def test_search_restaurants_no_match(self):
        search_res = self.client.get("/restaurants?q=NonExistentRestaurantXYZ98765")
        self.assertEqual(search_res.status_code, 200)
        self.assertEqual(search_res.json(), [])

    def test_list_restaurants_pagination_skip_and_limit(self):
        res_limit_1 = self.client.get("/restaurants?skip=0&limit=1")
        self.assertEqual(res_limit_1.status_code, 200)
        data = res_limit_1.json()
        self.assertLessEqual(len(data), 1)

    def test_list_restaurants_pagination_validation_errors(self):
        # Limit > 100
        res_high_limit = self.client.get("/restaurants?limit=101")
        self.assertEqual(res_high_limit.status_code, 422)

        # Limit < 1
        res_low_limit = self.client.get("/restaurants?limit=0")
        self.assertEqual(res_low_limit.status_code, 422)

        # Skip < 0
        res_negative_skip = self.client.get("/restaurants?skip=-1")
        self.assertEqual(res_negative_skip.status_code, 422)

    def test_get_restaurant_detail_success(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        detail_res = self.client.get(f"/restaurants/{first_id}")
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertEqual(detail["id"], first_id)
        self.assertIn("reviews", detail)
        self.assertIn("latest_analysis", detail)
        self.assertIn("review_count", detail)
        self.assertEqual(detail["review_count"], len(detail["reviews"]))

    def test_get_restaurant_detail_not_found(self):
        res = self.client.get("/restaurants/999999")
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["detail"].lower())

    def test_create_restaurant_success_and_cleanup(self):
        unique_place_id = f"test_place_{uuid.uuid4().hex[:10]}"
        payload = {
            "google_place_id": unique_place_id,
            "name": "Integration Test Bistro",
            "address": "456 Test Avenue, District 1",
            "google_rating": 4.7,
            "user_rating_count": 42
        }

        create_res = self.client.post("/restaurants", json=payload)
        self.assertEqual(create_res.status_code, 201)
        created = create_res.json()
        self.assertEqual(created["name"], payload["name"])
        self.assertEqual(created["google_place_id"], unique_place_id)
        self.assertEqual(created["review_count"], 0)

        # Register cleanup to keep database clean
        self.addCleanup(self._delete_restaurant, created["id"])

        # Verify it can be retrieved via detail endpoint
        detail_res = self.client.get(f"/restaurants/{created['id']}")
        self.assertEqual(detail_res.status_code, 200)
        self.assertEqual(detail_res.json()["name"], payload["name"])

    def test_create_restaurant_duplicate_place_id(self):
        list_res = self.client.get("/restaurants")
        existing_place_id = list_res.json()[0]["google_place_id"]

        payload = {
            "google_place_id": existing_place_id,
            "name": "Duplicate Place Bistro",
            "address": "123 Anywhere",
            "google_rating": 4.0
        }
        res = self.client.post("/restaurants", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("already exists", res.json()["detail"])

    def test_create_restaurant_validation_missing_fields(self):
        # Missing required google_place_id
        res_no_place = self.client.post("/restaurants", json={"name": "No Place ID"})
        self.assertEqual(res_no_place.status_code, 422)

        # Missing required name
        res_no_name = self.client.post("/restaurants", json={"google_place_id": "place_123"})
        self.assertEqual(res_no_name.status_code, 422)

    def test_get_restaurant_analyses_history(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        res = self.client.get(f"/restaurants/{first_id}/analyses")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_get_restaurant_analyses_history_not_found(self):
        res = self.client.get("/restaurants/999999/analyses")
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["detail"].lower())


class TestReviewsAPI(SeededIntegrationTestCase):
    """Tests for Review listing, pagination, and creation endpoints."""

    def _delete_review(self, review_id: int):
        with self.session_factory() as db:
            db.query(Review).filter(Review.id == review_id).delete()
            db.commit()

    def test_list_reviews_success(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        reviews_res = self.client.get(f"/restaurants/{first_id}/reviews")
        self.assertEqual(reviews_res.status_code, 200)
        reviews = reviews_res.json()
        self.assertIsInstance(reviews, list)
        self.assertTrue(reviews)
        if reviews:
            rev = reviews[0]
            self.assertIn("id", rev)
            self.assertIn("author_name", rev)
            self.assertIn("rating", rev)
            self.assertIn("text", rev)
            self.assertIn("published_at", rev)
            self.assertEqual(rev["restaurant_id"], first_id)

    def test_list_reviews_pagination(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        res = self.client.get(f"/restaurants/{first_id}/reviews?skip=0&limit=2")
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(len(res.json()), 2)

    def test_list_reviews_pagination_validation(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        res_high = self.client.get(f"/restaurants/{first_id}/reviews?limit=101")
        self.assertEqual(res_high.status_code, 422)

        res_low = self.client.get(f"/restaurants/{first_id}/reviews?limit=0")
        self.assertEqual(res_low.status_code, 422)

        res_neg_skip = self.client.get(f"/restaurants/{first_id}/reviews?skip=-1")
        self.assertEqual(res_neg_skip.status_code, 422)

    def test_list_reviews_restaurant_not_found(self):
        res = self.client.get("/restaurants/999999/reviews")
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["detail"].lower())

    def test_create_review_success_and_cleanup(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        ext_id = f"test_review_{uuid.uuid4().hex[:8]}"
        payload = {
            "restaurant_id": first_id,
            "author_name": "Food Critic Jane",
            "rating": 5.0,
            "text": "The signature dish was seasoned to perfection. Friendly attentive staff!",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "external_review_id": ext_id
        }

        res = self.client.post(f"/restaurants/{first_id}/reviews", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["restaurant_id"], first_id)
        self.assertEqual(data["author_name"], payload["author_name"])
        self.assertEqual(data["rating"], payload["rating"])
        self.assertEqual(data["text"], payload["text"])

        # Ensure cleanup
        self.addCleanup(self._delete_review, data["id"])

        # Verify the review appears in review list
        reviews_res = self.client.get(f"/restaurants/{first_id}/reviews")
        self.assertEqual(reviews_res.status_code, 200)
        self.assertTrue(any(r["id"] == data["id"] for r in reviews_res.json()))

    def test_create_review_restaurant_not_found(self):
        payload = {
            "restaurant_id": 999999,
            "author_name": "Ghost Reviewer",
            "rating": 3.0,
            "text": "Does not exist",
            "published_at": datetime.now(timezone.utc).isoformat()
        }
        res = self.client.post("/restaurants/999999/reviews", json=payload)
        self.assertEqual(res.status_code, 404)

    def test_create_review_validation_errors(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        # Missing rating
        payload_no_rating = {
            "restaurant_id": first_id,
            "author_name": "Jane",
            "text": "Good food",
            "published_at": datetime.now(timezone.utc).isoformat()
        }
        res = self.client.post(f"/restaurants/{first_id}/reviews", json=payload_no_rating)
        self.assertEqual(res.status_code, 422)

        # Missing author_name
        payload_no_author = {
            "restaurant_id": first_id,
            "rating": 4.0,
            "text": "Good food",
            "published_at": datetime.now(timezone.utc).isoformat()
        }
        res = self.client.post(f"/restaurants/{first_id}/reviews", json=payload_no_author)
        self.assertEqual(res.status_code, 422)


class TestAnalysisAPIAndService(SeededIntegrationTestCase):
    """Tests for AI analysis endpoints, caching, force refresh, and OpenAI fallback handling."""

    def test_trigger_analysis_restaurant_not_found(self):
        res = self.client.post("/restaurants/999999/analyze", json={"force_refresh": True})
        self.assertEqual(res.status_code, 404)

    def test_trigger_analysis_caching_behavior(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        with patch("app.services.analysis.settings.OPENAI_API_KEY", ""):
            # First call with force_refresh to guarantee an initial analysis exists
            first_res = self.client.post(f"/restaurants/{first_id}/analyze", json={"force_refresh": True})
            self.assertEqual(first_res.status_code, 200)
            first_data = first_res.json()
            analysis_id_1 = first_data["id"]

            # Second call without force_refresh should return the cached analysis
            second_res = self.client.post(f"/restaurants/{first_id}/analyze", json={"force_refresh": False})
            self.assertEqual(second_res.status_code, 200)
            second_data = second_res.json()
            analysis_id_2 = second_data["id"]

            # IDs must match indicating cache hit
            self.assertEqual(analysis_id_1, analysis_id_2)

    def test_trigger_analysis_force_refresh(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        with patch("app.services.analysis.settings.OPENAI_API_KEY", ""):
            # First call
            res1 = self.client.post(f"/restaurants/{first_id}/analyze", json={"force_refresh": True})
            self.assertEqual(res1.status_code, 200)
            id_1 = res1.json()["id"]

            # Force refresh call creates a new analysis record
            res2 = self.client.post(f"/restaurants/{first_id}/analyze", json={"force_refresh": True})
            self.assertEqual(res2.status_code, 200)
            id_2 = res2.json()["id"]

            self.assertNotEqual(id_1, id_2)
            self.assertGreater(id_2, id_1)

    def test_trigger_analysis_with_mocked_openai_success(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        mock_payload = {
            "overall_sentiment": "POSITIVE",
            "summary": "Mocked LLM analysis output demonstrating great food and service.",
            "estimated_rating_trend": "IMPROVING",
            "aspect_breakdown": [
                {
                    "aspect": "food",
                    "sentiment": "POSITIVE",
                    "score": 4.8,
                    "summary": "Tasting notes praised widely.",
                    "highlights": ["crispy texture"]
                }
            ],
            "prioritized_improvements": [],
            "strengths_to_keep": [
                {
                    "aspect": "food",
                    "strength": "High culinary craftsmanship",
                    "marketing_tip": "Highlight freshness in campaign"
                }
            ]
        }

        with patch("app.services.analysis.settings.OPENAI_API_KEY", "test-key-mocked"):
            with patch("app.services.analysis.analyze_with_openai", return_value=("POSITIVE", mock_payload)):
                res = self.client.post(
                    f"/restaurants/{first_id}/analyze",
                    json={"force_refresh": True, "model": "gpt-4o-mini"}
                )
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["overall_sentiment"], "POSITIVE")
                self.assertEqual(data["model"], "gpt-4o-mini")
                self.assertEqual(data["result_json"]["summary"], mock_payload["summary"])

    def test_trigger_analysis_fallback_when_openai_fails(self):
        list_res = self.client.get("/restaurants")
        first_id = list_res.json()[0]["id"]

        with patch("app.services.analysis.settings.OPENAI_API_KEY", "test-key-mocked"):
            with patch("app.services.analysis.analyze_with_openai", side_effect=RuntimeError("Simulated LLM outage")):
                res = self.client.post(f"/restaurants/{first_id}/analyze", json={"force_refresh": True})
                # Resilient design: should NOT return 500 error; falls back gracefully
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["model"], "heuristic-fallback")
                self.assertIn("overall_sentiment", data)
                self.assertIn("result_json", data)
                self.assertIn("aspect_breakdown", data["result_json"])


class TestHeuristicAnalysisEngine(unittest.TestCase):
    """Unit tests for the heuristic fallback analysis algorithm in app.services.analysis."""

    def _create_mock_review(self, rating: float, text: str) -> Review:
        now = datetime.now(timezone.utc)
        return Review(
            id=1,
            restaurant_id=1,
            author_name="Tester",
            rating=rating,
            text=text,
            published_at=now
        )

    def test_empty_reviews(self):
        sentiment, result = generate_mock_analysis("Empty Cafe", [])
        self.assertEqual(sentiment, "NEUTRAL")
        self.assertEqual(result["overall_sentiment"], "NEUTRAL")
        self.assertEqual(result["summary"], "No reviews available yet to analyze.")
        self.assertEqual(result["estimated_rating_trend"], "STABLE")
        self.assertEqual(result["aspect_breakdown"], [])
        self.assertEqual(result["prioritized_improvements"], [])
        self.assertEqual(result["strengths_to_keep"], [])

    def test_positive_reviews_evaluation(self):
        reviews = [
            self._create_mock_review(5.0, "The food and dish was delicious and taste was amazing."),
            self._create_mock_review(5.0, "Attentive friendly staff and exceptional quick service."),
            self._create_mock_review(5.0, "Super clean tables, spotless hygiene and restroom."),
            self._create_mock_review(4.5, "Cozy ambience with relaxing background music and decor."),
            self._create_mock_review(4.5, "Affordable price and great value for the high quality.")
        ]
        sentiment, result = generate_mock_analysis("Top Dining", reviews)
        self.assertEqual(sentiment, "POSITIVE")
        self.assertEqual(result["overall_sentiment"], "POSITIVE")
        self.assertGreater(len(result["strengths_to_keep"]), 0)

        # Verify all 6 aspects exist in aspect_breakdown
        aspect_names = {a["aspect"] for a in result["aspect_breakdown"]}
        self.assertEqual(aspect_names, {"food", "service", "wait_time", "hygiene", "ambience", "price"})

        # Food and service should be POSITIVE
        for aspect in result["aspect_breakdown"]:
            if aspect["aspect"] in ["food", "service"]:
                self.assertEqual(aspect["sentiment"], "POSITIVE")
                self.assertGreaterEqual(aspect["score"], 4.0)

    def test_negative_reviews_generates_high_priority_improvements(self):
        reviews = [
            self._create_mock_review(1.0, "Awful wait time! We waited in line and queue for 90 minutes delay."),
            self._create_mock_review(1.5, "Rude waiter and terrible slow service from staff."),
            self._create_mock_review(2.0, "Dirty table and dirty restroom with bad hygiene and smell."),
            self._create_mock_review(1.0, "Ridiculously expensive price, definitely not worth the cost.")
        ]
        sentiment, result = generate_mock_analysis("Troubled Diner", reviews)
        self.assertEqual(sentiment, "NEGATIVE")
        self.assertEqual(result["overall_sentiment"], "NEGATIVE")

        # Verify high priority improvements generated
        improvements = result["prioritized_improvements"]
        self.assertGreater(len(improvements), 0)
        self.assertTrue(any(imp["priority"] == "HIGH" for imp in improvements))
        self.assertTrue(any("wait_time" in imp["aspect"] or "service" in imp["aspect"] or "hygiene" in imp["aspect"] for imp in improvements))

    def test_improving_rating_trend(self):
        reviews = [
            self._create_mock_review(1.0, "Terrible food and bad service"),
            self._create_mock_review(2.0, "Slow service"),
            self._create_mock_review(2.0, "Cramped and dirty"),
            self._create_mock_review(5.0, "Under new management, delicious food!"),
            self._create_mock_review(5.0, "Great staff and friendly service"),
            self._create_mock_review(5.0, "Spotless clean and wonderful atmosphere")
        ]
        reviews[0].published_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        reviews[1].published_at = datetime(2025, 1, 15, tzinfo=timezone.utc)
        reviews[2].published_at = datetime(2025, 2, 1, tzinfo=timezone.utc)
        reviews[3].published_at = datetime(2025, 3, 1, tzinfo=timezone.utc)
        reviews[4].published_at = datetime(2025, 3, 15, tzinfo=timezone.utc)
        reviews[5].published_at = datetime(2025, 4, 1, tzinfo=timezone.utc)

        _, result = generate_mock_analysis("Revamped Bistro", reviews)
        self.assertEqual(result["estimated_rating_trend"], "IMPROVING")

    def test_declining_rating_trend(self):
        reviews = [
            self._create_mock_review(5.0, "Awesome quality and great food"),
            self._create_mock_review(5.0, "Best service in town"),
            self._create_mock_review(5.0, "Super clean and cozy"),
            self._create_mock_review(1.0, "Quality dropped completely, awful food"),
            self._create_mock_review(1.5, "Waited 1 hour, rude waiter"),
            self._create_mock_review(2.0, "Dirty table and noisy")
        ]
        reviews[0].published_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        reviews[1].published_at = datetime(2025, 1, 15, tzinfo=timezone.utc)
        reviews[2].published_at = datetime(2025, 2, 1, tzinfo=timezone.utc)
        reviews[3].published_at = datetime(2025, 3, 1, tzinfo=timezone.utc)
        reviews[4].published_at = datetime(2025, 3, 15, tzinfo=timezone.utc)
        reviews[5].published_at = datetime(2025, 4, 1, tzinfo=timezone.utc)

        _, result = generate_mock_analysis("Declining Cafe", reviews)
        self.assertEqual(result["estimated_rating_trend"], "DECLINING")

    def test_stable_rating_trend(self):
        reviews = [
            self._create_mock_review(4.0, "Consistent good food"),
            self._create_mock_review(4.0, "Pleasant staff service"),
            self._create_mock_review(4.0, "Nice ambience"),
            self._create_mock_review(4.0, "Reasonable price"),
            self._create_mock_review(4.0, "Clean restaurant")
        ]
        _, result = generate_mock_analysis("Steady Eatery", reviews)
        self.assertEqual(result["estimated_rating_trend"], "STABLE")


class TestSyncAPIAndService(SeededIntegrationTestCase):
    """Tests for Sync targets, sync execution, sync runs history, and external place detail fetchers."""

    def _delete_sync_target(self, target_id: int):
        with self.session_factory() as db:
            db.query(SyncTarget).filter(SyncTarget.id == target_id).delete()
            db.commit()

    def test_list_sync_targets(self):
        res = self.client.get("/sync/targets")
        self.assertEqual(res.status_code, 200)
        targets = res.json()
        self.assertIsInstance(targets, list)
        self.assertTrue(targets)
        if targets:
            self.assertIn("id", targets[0])
            self.assertIn("target_type", targets[0])
            self.assertIn("value", targets[0])

    def test_create_sync_target_success_and_cleanup(self):
        unique_val = f"ChIJ_test_{uuid.uuid4().hex[:8]}"
        payload = {
            "target_type": "place_id",
            "value": unique_val,
            "language_code": "en",
            "is_active": True
        }

        res = self.client.post("/sync/targets", json=payload)
        self.assertEqual(res.status_code, 201)
        created = res.json()
        self.assertEqual(created["value"], unique_val)
        self.assertEqual(created["target_type"], "place_id")
        self.assertTrue(created["is_active"])

        self.addCleanup(self._delete_sync_target, created["id"])

        # Check target is listed
        list_res = self.client.get("/sync/targets")
        self.assertEqual(list_res.status_code, 200)
        self.assertTrue(any(t["id"] == created["id"] for t in list_res.json()))

    def test_create_sync_target_validation_errors(self):
        # Missing required target_type
        res_no_type = self.client.post("/sync/targets", json={"value": "test_val"})
        self.assertEqual(res_no_type.status_code, 422)

        # Missing required value
        res_no_val = self.client.post("/sync/targets", json={"target_type": "place_id"})
        self.assertEqual(res_no_val.status_code, 422)

    def test_trigger_sync_all_targets(self):
        res = self.client.post("/sync/run")
        self.assertEqual(res.status_code, 200)
        run_data = res.json()
        self.assertEqual(run_data["status"], "COMPLETED")
        self.assertIn("restaurants_upserted", run_data)
        self.assertIn("reviews_upserted", run_data)
        self.assertGreaterEqual(run_data["restaurants_upserted"], 0)

    def test_trigger_sync_single_target_success(self):
        targets_res = self.client.get("/sync/targets")
        targets = targets_res.json()
        self.assertTrue(targets)
        if targets:
            target_id = targets[0]["id"]
            res = self.client.post(f"/sync/run?target_id={target_id}")
            self.assertEqual(res.status_code, 200)
            run_data = res.json()
            self.assertEqual(run_data["status"], "COMPLETED")

    def test_trigger_sync_target_not_found(self):
        res = self.client.post("/sync/run?target_id=999999")
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["detail"].lower())

    def test_list_sync_runs(self):
        self.assertEqual(self.client.post("/sync/run").status_code, 200)
        res = self.client.get("/sync/runs")
        self.assertEqual(res.status_code, 200)
        runs = res.json()
        self.assertIsInstance(runs, list)
        if runs:
            first = runs[0]
            self.assertIn("id", first)
            self.assertIn("status", first)
            self.assertIn("started_at", first)

    def test_list_sync_runs_pagination(self):
        self.assertEqual(self.client.post("/sync/run").status_code, 200)
        res = self.client.get("/sync/runs?skip=0&limit=1")
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(len(res.json()), 1)

        # Invalid limit
        res_inv = self.client.get("/sync/runs?limit=101")
        self.assertEqual(res_inv.status_code, 422)

    def test_fetch_from_google_places_success_mocked(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "result": {
                "place_id": "test_place_abc",
                "name": "Bánh Mì Test",
                "formatted_address": "789 Street",
                "rating": 4.6,
                "user_ratings_total": 50,
                "reviews": []
            }
        }
        with patch("httpx.get", return_value=mock_response):
            result = fetch_from_google_places("test_place_abc", "fake_api_key", "en")
            self.assertIsNotNone(result)
            self.assertEqual(result["place_id"], "test_place_abc")
            self.assertEqual(result["name"], "Bánh Mì Test")

    def test_fetch_from_google_places_error_status_mocked(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "REQUEST_DENIED",
            "error_message": "The provided API key is invalid."
        }
        with patch("httpx.get", return_value=mock_response):
            result = fetch_from_google_places("test_place_abc", "fake_api_key", "en")
            self.assertIsNone(result)

    def test_fetch_from_google_places_network_exception(self):
        with patch("httpx.get", side_effect=Exception("Connection timeout")):
            result = fetch_from_google_places("test_place_abc", "fake_api_key", "en")
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
