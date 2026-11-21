"""25 acceptance cases plus unit and API integration checks.

Existing defects remain visible failures; no acceptance cases are skipped or
marked as expected failures, and no backend behavior is patched to pass them.
"""

from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# Also support the repository's historical command from the root directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import support first so safe settings are loaded before the application.
from tests.support import BackendTestCase, EXPECTED_ANALYSIS, settings
import httpx
from app.models import Analysis, Notification, Restaurant, Review, SyncRun, SyncTarget
from app.schemas import (
    AnalysisResponse, AnalysisResultPayload, NotificationResponse, RestaurantDetailResponse,
    RestaurantResponse, ReviewResponse, SyncRunResponse, SyncTargetResponse,
)
from app.services.analysis import generate_mock_analysis, get_or_run_restaurant_analysis
from app.services.sync import execute_sync_job


class TestBackendAcceptance(BackendTestCase):
    def test_be_01_p0_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_be_02_p0_restaurant_list_schema_and_counts(self) -> None:
        self.assertEqual(self.client.get("/restaurants").json(), [])
        first = self.restaurant()
        second = self.restaurant(google_place_id="other-place", name="Empty Cafe")
        self.review(first["id"])
        self.review(first["id"], text="Second guest")
        response = self.client.get("/restaurants")
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        for row in rows:
            RestaurantResponse.model_validate(row)
        self.assertEqual({row["id"]: row["review_count"] for row in rows}, {first["id"]: 2, second["id"]: 0})

    def test_be_03_p0_case_insensitive_name_and_address_search(self) -> None:
        match = self.restaurant()
        self.restaurant(google_place_id="unrelated", name="Other Cafe", address="9 Pine Road")
        for query in ("cEdAr", "MARKET street"):
            with self.subTest(query=query):
                response = self.client.get("/restaurants", params={"q": query})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row["id"] for row in response.json()], [match["id"]])
        self.assertEqual(self.client.get("/restaurants?q=no-such-place").json(), [])

    def test_be_04_p1_pagination_bounds(self) -> None:
        for query in ({"skip": -1}, {"limit": 0}, {"limit": 101}):
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/restaurants", params=query).status_code, 422)
        created = [self.restaurant(google_place_id=f"place-{index}", name=name)
                   for index, name in enumerate(("Zebra Cafe", "Apple Cafe", "Maple Cafe"))]
        response = self.client.get("/restaurants", params={"skip": 0, "limit": 100})
        self.assertEqual(response.status_code, 200)
        ordered_ids = [row["id"] for row in response.json()]
        self.assertCountEqual(ordered_ids, [row["id"] for row in created])
        # No sort field/order is documented: pages must preserve full-list order.
        pages = {}
        for skip, limit in ((0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2), (3, 1)):
            with self.subTest(skip=skip, limit=limit):
                response = self.client.get("/restaurants", params={"skip": skip, "limit": limit})
                self.assertEqual(response.status_code, 200)
                pages[skip, limit] = [row["id"] for row in response.json()]
                self.assertEqual(pages[skip, limit], ordered_ids[skip:skip + limit])
        self.assertTrue(set(pages[0, 1]).isdisjoint(pages[1, 1]))
        self.assertTrue(set(pages[1, 1]).isdisjoint(pages[2, 1]))
        self.assertTrue(set(pages[0, 2]).isdisjoint(pages[2, 2]))

    def test_be_05_p0_detail_reviews_latest_analysis_and_not_found(self) -> None:
        restaurant = self.restaurant()
        review = self.review(restaurant["id"])
        self.analysis_row(restaurant["id"], datetime(2020, 1, 1))
        latest = self.analysis_row(restaurant["id"], datetime(2020, 1, 3))
        response = self.client.get(f'/restaurants/{restaurant["id"]}')
        self.assertEqual(response.status_code, 200)
        detail = response.json()
        RestaurantDetailResponse.model_validate(detail)
        self.assertEqual(detail["review_count"], 1)
        self.assertEqual([row["id"] for row in detail["reviews"]], [review["id"]])
        self.assertEqual(detail["latest_analysis"]["id"], latest.id)
        self.assertEqual(self.client.get("/restaurants/999999").status_code, 404)

    def test_be_06_p0_create_restaurant_and_duplicate(self) -> None:
        row = self.restaurant()
        self.assertIsNotNone(self.db.get(Restaurant, row["id"]))
        response = self.client.post("/restaurants", json={"google_place_id": row["google_place_id"], "name": "Duplicate"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.query(Restaurant).count(), 1)

    def test_be_07_p1_restaurant_required_fields_and_ratings(self) -> None:
        for payload in ({}, {"google_place_id": "missing-name"}, {"name": "Missing ID"}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/restaurants", json=payload).status_code, 422)
        for index, rating in enumerate((-1, 0, 5.1, "invalid")):
            with self.subTest(rating=rating):
                response = self.client.post("/restaurants", json={"google_place_id": f"bad-rating-{index}", "name": "Invalid", "google_rating": rating})
                self.assertEqual(response.status_code, 422, response.text)

    def test_be_08_p0_review_creation_persists(self) -> None:
        restaurant = self.restaurant()
        row = self.review(restaurant["id"], external_review_id="unique-review", rating=3.5)
        ReviewResponse.model_validate(row)
        stored = self.db.get(Review, row["id"])
        self.assertEqual(stored.restaurant_id, restaurant["id"])
        self.assertEqual(stored.external_review_id, "unique-review")
        self.assertEqual(stored.rating, 3.5)
        self.assertEqual(stored.text, row["text"])

    def test_be_09_p0_reviews_newest_published_first(self) -> None:
        restaurant = self.restaurant()
        old = self.review(restaurant["id"], published_at="2020-01-01T00:00:00Z")
        new = self.review(restaurant["id"], published_at="2020-01-03T00:00:00Z")
        middle = self.review(restaurant["id"], published_at="2020-01-02T00:00:00Z")
        response = self.client.get(f'/restaurants/{restaurant["id"]}/reviews')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()], [new["id"], middle["id"], old["id"]])

    def test_be_10_p1_review_missing_restaurant_and_invalid_rating(self) -> None:
        self.assertEqual(self.client.get("/restaurants/999999/reviews").status_code, 404)
        self.assertEqual(self.client.post("/restaurants/999999/reviews", json=self.review_payload(999999)).status_code, 404)
        restaurant = self.restaurant()
        for rating in (0, 5.1, "invalid"):
            with self.subTest(rating=rating):
                response = self.client.post(f'/restaurants/{restaurant["id"]}/reviews', json=self.review_payload(restaurant["id"], rating=rating))
                self.assertEqual(response.status_code, 422, response.text)

    def test_be_11_p1_duplicate_external_review_is_client_error(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"], external_review_id="same-external-id")
        response = self.client.post(f'/restaurants/{restaurant["id"]}/reviews', json=self.review_payload(restaurant["id"], external_review_id="same-external-id"))
        with self.subTest(check="only one row is persisted"):
            self.assertEqual(self.db.query(Review).count(), 1)
        self.assertIn(response.status_code, (400, 409), response.text)

    def test_be_12_p0_structured_analysis_response(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"])
        with self.openai_response() as completion:
            response = self.client.post(f'/restaurants/{restaurant["id"]}/analyze', json={})
            self.assertEqual(response.status_code, 200, response.text)
            row = response.json()
            AnalysisResponse.model_validate(row)
            AnalysisResultPayload.model_validate(row["result_json"])
            self.assertEqual(row["result_json"], EXPECTED_ANALYSIS)
            self.assertEqual(row["overall_sentiment"], "MIXED")
            self.assertEqual(row["review_count"], 1)
            self.assertEqual(self.db.get(Analysis, row["id"]).result_json, EXPECTED_ANALYSIS)
            completion.assert_called_once()
            self.assertIn("Fresh food", completion.call_args.kwargs["messages"][1]["content"])

    def test_be_13_p0_no_reviews_neutral_stable_empty_insights(self) -> None:
        restaurant = self.restaurant()
        response = self.client.post(f'/restaurants/{restaurant["id"]}/analyze')
        self.assertEqual(response.status_code, 200)
        row = response.json()
        result = row["result_json"]
        self.assertEqual(row["review_count"], 0)
        self.assertEqual(result["overall_sentiment"], "NEUTRAL")
        self.assertEqual(result["estimated_rating_trend"], "STABLE")
        for key in ("aspect_breakdown", "prioritized_improvements", "strengths_to_keep"):
            self.assertEqual(result[key], [])

    def test_be_14_p0_missing_key_uses_heuristic_without_request(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"])
        response = self.client.post(f'/restaurants/{restaurant["id"]}/analyze')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model"], "heuristic-mock")
        AnalysisResultPayload.model_validate(response.json()["result_json"])
        self.openai_guard.assert_not_called()

    def test_be_15_p0_openai_timeout_and_exception_fallback(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"])
        for error in (httpx.ReadTimeout("simulated timeout"), RuntimeError("simulated provider outage")):
            with self.subTest(error=type(error).__name__), self.openai_response() as completion:
                completion.side_effect = error
                response = self.client.post(f'/restaurants/{restaurant["id"]}/analyze', json={"force_refresh": True})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["model"], "heuristic-fallback")
                AnalysisResultPayload.model_validate(response.json()["result_json"])
                completion.assert_called_once()

    def test_be_16_p0_valid_cache_does_not_call_llm_again(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"])
        with self.openai_response() as completion:
            first = self.client.post(f'/restaurants/{restaurant["id"]}/analyze')
            second = self.client.post(f'/restaurants/{restaurant["id"]}/analyze')
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(first.json()["id"], second.json()["id"])
            completion.assert_called_once()

    def test_be_17_p0_force_refresh_bypasses_cache(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"])
        with self.openai_response() as completion:
            first = self.client.post(f'/restaurants/{restaurant["id"]}/analyze')
            second = self.client.post(f'/restaurants/{restaurant["id"]}/analyze', json={"force_refresh": True})
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            self.assertNotEqual(first.json()["id"], second.json()["id"])
            self.assertEqual(completion.call_count, 2)
            self.assertEqual(self.db.query(Analysis).count(), 2)

    def test_be_18_p0_backdated_review_invalidates_analysis_and_count(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"])
        with self.openai_response() as completion:
            first = self.client.post(f'/restaurants/{restaurant["id"]}/analyze').json()
            self.review(restaurant["id"], published_at="2019-01-01T00:00:00Z", rating=1.0)
            response = self.client.post(f'/restaurants/{restaurant["id"]}/analyze')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.get("/restaurants").json()[0]["review_count"], 2)
            with self.subTest(check="analysis includes both reviews"):
                self.assertEqual(response.json()["review_count"], 2)
            with self.subTest(check="new snapshot"):
                self.assertNotEqual(first["id"], response.json()["id"])
            self.assertEqual(completion.call_count, 2)

    def test_be_19_p1_analysis_history_newest_first_and_not_found(self) -> None:
        restaurant = self.restaurant()
        self.assertEqual(self.client.get(f'/restaurants/{restaurant["id"]}/analyses').json(), [])
        old = self.analysis_row(restaurant["id"], datetime(2020, 1, 1))
        new = self.analysis_row(restaurant["id"], datetime(2020, 1, 2))
        response = self.client.get(f'/restaurants/{restaurant["id"]}/analyses')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()], [new.id, old.id])
        self.assertEqual(self.client.get("/restaurants/999999/analyses").status_code, 404)

    def test_be_20_p1_malformed_llm_output_is_not_persisted(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"])
        cases = {"invalid JSON": "{not-json", "missing fields": json.dumps({"overall_sentiment": "POSITIVE"})}
        for field in ("overall_sentiment", "estimated_rating_trend"):
            payload = deepcopy(EXPECTED_ANALYSIS)
            payload[field] = "INVALID"
            cases[field] = json.dumps(payload)
        payload = deepcopy(EXPECTED_ANALYSIS)
        payload["prioritized_improvements"][0]["priority"] = "URGENT"
        cases["invalid priority"] = json.dumps(payload)
        payload = deepcopy(EXPECTED_ANALYSIS)
        payload["aspect_breakdown"][0]["sentiment"] = "INVALID"
        cases["invalid aspect sentiment"] = json.dumps(payload)
        for label, content in cases.items():
            with self.subTest(case=label), self.openai_response(content):
                response = self.client.post(f'/restaurants/{restaurant["id"]}/analyze', json={"force_refresh": True})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["model"], "heuristic-fallback", "Invalid output must use the safe heuristic fallback")
                result = response.json()["result_json"]
                AnalysisResultPayload.model_validate(result)
                self.assertEqual(self.db.get(Analysis, response.json()["id"]).result_json, result)

    def test_be_21_p0_create_list_persisted_sync_targets(self) -> None:
        self.assertEqual(self.client.get("/sync/targets").json(), [])
        target = self.target(language_code="vi", is_active=False)
        SyncTargetResponse.model_validate(target)
        self.assertEqual(self.client.get("/sync/targets").json(), [target])
        stored = self.db.get(SyncTarget, target["id"])
        self.assertEqual(stored.language_code, "vi")
        self.assertFalse(stored.is_active)
        self.assertEqual(stored.value, target["value"])

    def test_be_22_p0_mock_sync_without_credentials(self) -> None:
        target = self.target()
        response = self.client.post("/sync/run", params={"target_id": target["id"]})
        self.assertEqual(response.status_code, 200)
        row = response.json()
        SyncRunResponse.model_validate(row)
        self.assertEqual(row["status"], "COMPLETED")
        self.assertEqual((row["restaurants_upserted"], row["reviews_upserted"]), (1, 3))
        self.assertEqual(self.db.query(Restaurant).count(), 1)
        self.assertEqual(self.db.query(Review).count(), 3)
        self.assertIsNotNone(self.db.get(SyncTarget, target["id"]).last_synced_at)
        self.google_guard.assert_not_called()

    def test_be_23_p0_repeated_sync_is_idempotent(self) -> None:
        self.target()
        first = self.client.post("/sync/run").json()
        restaurant_ids = [row.id for row in self.db.query(Restaurant).all()]
        review_ids = [row.id for row in self.db.query(Review).all()]
        second = self.client.post("/sync/run").json()
        self.assertEqual(first["status"], "COMPLETED")
        self.assertEqual(second["status"], "COMPLETED")
        self.assertEqual(second["reviews_upserted"], 0)
        self.assertEqual([row.id for row in self.db.query(Restaurant).all()], restaurant_ids)
        self.assertEqual([row.id for row in self.db.query(Review).all()], review_ids)
        self.assertEqual(self.db.query(SyncRun).count(), 2)

    def test_be_24_p1_skip_inactive_and_missing_target(self) -> None:
        self.target(value="active-target")
        inactive = self.target(value="inactive-target", is_active=False)
        response = self.client.post("/sync/run")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["restaurants_upserted"], 1)
        self.assertIsNone(self.db.get(SyncTarget, inactive["id"]).last_synced_at)
        self.assertIsNone(self.db.query(Restaurant).filter_by(google_place_id="inactive-target").first())
        self.assertEqual(self.client.post("/sync/run?target_id=999999").status_code, 404)

    def _assert_failed_sync(self, provider_result: dict | Exception) -> None:
        target = self.target()
        previous_last_synced = datetime(2020, 1, 1)
        self.db.get(SyncTarget, target["id"]).last_synced_at = previous_last_synced
        self.db.commit()
        before = (self.db.query(Restaurant).count(), self.db.query(Review).count())
        self.assertEqual(before, (0, 0), "Each provider scenario requires an empty database")
        with patch.object(settings, "GOOGLE_PLACES_API_KEY", "test-only-google-key"), patch("app.services.sync.httpx.get") as provider:
            if isinstance(provider_result, Exception):
                provider.side_effect = provider_result
            else:
                provider.return_value = httpx.Response(200, json=provider_result, request=httpx.Request("GET", "https://provider.invalid"))
            response = self.client.post("/sync/run", params={"target_id": target["id"]})
            provider.assert_called_once()
        self.assertEqual(response.status_code, 200)
        run = response.json()
        self.db.expire_all()
        stored = self.db.get(SyncRun, run["id"])
        with self.subTest(check="failed response status"):
            self.assertEqual(run["status"], "FAILED")
        with self.subTest(check="persisted failed status"):
            self.assertEqual(stored.status, "FAILED")
        with self.subTest(check="error persistence"):
            self.assertTrue(run["error_message"])
            self.assertEqual(stored.error_message, run["error_message"])
        with self.subTest(check="no partial imports"):
            self.assertEqual((self.db.query(Restaurant).count(), self.db.query(Review).count()), before)
        with self.subTest(check="last_synced_at is unchanged"):
            self.assertEqual(self.db.get(SyncTarget, target["id"]).last_synced_at, previous_last_synced)
        with self.subTest(check="import counters"):
            self.assertEqual((run["restaurants_upserted"], run["reviews_upserted"]), (0, 0))
            self.assertEqual((stored.restaurants_upserted, stored.reviews_upserted), (0, 0))
        self.assertIsNotNone(stored.finished_at)

    def test_be_25_p1_provider_timeout_persists_failed_status(self) -> None:
        self._assert_failed_sync(httpx.ReadTimeout("simulated Google timeout"))

    def test_be_25_p1_provider_denial_persists_failed_status(self) -> None:
        self._assert_failed_sync({"status": "REQUEST_DENIED", "error_message": "internal-provider-detail"})

    def test_be_25_p1_missing_result_persists_failed_status(self) -> None:
        self._assert_failed_sync({"status": "OK"})

    def test_be_25_p1_invalid_review_has_no_partial_import(self) -> None:
        self._assert_failed_sync({"status": "OK", "result": {"place_id": "bad-place", "name": "Bad provider",
                                "reviews": [{"time": 1577836800, "rating": "not-a-rating"}]}})


class TestHeuristicAnalysis(unittest.TestCase):
    def reviews(self, ratings: list[float]) -> list[Review]:
        return [Review(rating=rating, text="Food service wait clean atmosphere price",
                       published_at=datetime(2020, 1, 1) + timedelta(days=index))
                for index, rating in enumerate(ratings)]

    def test_empty_reviews_are_neutral(self) -> None:
        sentiment, result = generate_mock_analysis("Empty Cafe", [])
        self.assertEqual(sentiment, "NEUTRAL")
        self.assertEqual(result["estimated_rating_trend"], "STABLE")
        self.assertEqual(result["prioritized_improvements"], [])
        self.assertEqual(result["strengths_to_keep"], [])

    def test_sentiment_thresholds_and_recommendation_priorities(self) -> None:
        for ratings, sentiment, priority in (([1, 2], "NEGATIVE", "HIGH"), ([3, 3], "MIXED", "MEDIUM"), ([4, 5], "POSITIVE", None)):
            with self.subTest(ratings=ratings):
                actual, result = generate_mock_analysis("Test Cafe", self.reviews(ratings))
                self.assertEqual(actual, sentiment)
                AnalysisResultPayload.model_validate(result)
                self.assertEqual({row["aspect"] for row in result["aspect_breakdown"]}, {"food", "service", "wait_time", "hygiene", "ambience", "price"})
                if priority:
                    self.assertTrue(result["prioritized_improvements"])
                    self.assertTrue(all(row["priority"] == priority for row in result["prioritized_improvements"]))
                else:
                    self.assertEqual(result["prioritized_improvements"], [])
                    self.assertTrue(result["strengths_to_keep"])

    def test_rating_trends_use_publication_order(self) -> None:
        for ratings, trend in (([1, 2, 4, 5], "IMPROVING"), ([5, 4, 2, 1], "DECLINING"), ([3, 3, 3, 3], "STABLE"), ([4], "STABLE")):
            with self.subTest(ratings=ratings):
                _, result = generate_mock_analysis("Trend Cafe", list(reversed(self.reviews(ratings))))
                self.assertEqual(result["estimated_rating_trend"], trend)


class TestCacheUnit(BackendTestCase):
    def test_cache_reuses_unchanged_review_snapshot(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"])
        first = get_or_run_restaurant_analysis(self.db, restaurant["id"])
        second = get_or_run_restaurant_analysis(self.db, restaurant["id"])
        self.assertEqual(first.id, second.id)

    def test_cache_invalidates_when_first_review_is_backdated(self) -> None:
        restaurant = self.restaurant()
        first = get_or_run_restaurant_analysis(self.db, restaurant["id"])
        self.review(restaurant["id"], published_at="2000-01-01T00:00:00Z")
        second = get_or_run_restaurant_analysis(self.db, restaurant["id"])
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(second.review_count, 1)

    def test_cache_reuses_unchanged_future_dated_review(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"], published_at="2099-01-01T00:00:00Z")
        first = get_or_run_restaurant_analysis(self.db, restaurant["id"])
        second = get_or_run_restaurant_analysis(self.db, restaurant["id"])
        self.assertEqual(first.id, second.id)


class TestIntegrationSupport(BackendTestCase):
    def test_docs_publish_all_required_endpoints(self) -> None:
        self.assertEqual(self.client.get("/docs").status_code, 200)
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        expected = {"/health": {"get"}, "/restaurants": {"get", "post"},
                    "/restaurants/{restaurant_id}": {"get"},
                    "/restaurants/{restaurant_id}/reviews": {"get", "post"},
                    "/restaurants/{restaurant_id}/analyze": {"post"},
                    "/restaurants/{restaurant_id}/analyses": {"get"},
                    "/sync/targets": {"get", "post"}, "/sync/run": {"post"}, "/sync/runs": {"get"}}
        for path, methods in expected.items():
            with self.subTest(path=path):
                self.assertTrue(methods.issubset(paths[path]))

    def test_browser_origin_cors_preflight_and_requests(self) -> None:
        origin = "http://localhost:5173"
        response = self.client.options("/restaurants/1/analyze", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)
        response = self.client.get("/restaurants", headers={"Origin": origin})
        self.assertEqual(response.headers["access-control-allow-origin"], origin)
        response = self.client.get("/restaurants", headers={"Origin": "https://unconfigured.invalid"})
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_search_reviews_analysis_recommendations_contract(self) -> None:
        restaurant = self.restaurant()
        self.review(restaurant["id"], rating=2.0, text="Slow service and long wait for food")
        headers = {"Origin": "http://localhost:5173"}
        rows = self.client.get("/restaurants?q=cedar", headers=headers).json()
        self.assertEqual([row["id"] for row in rows], [restaurant["id"]])
        detail = self.client.get(f'/restaurants/{restaurant["id"]}', headers=headers).json()
        self.assertEqual(len(detail["reviews"]), 1)
        response = self.client.post(f'/restaurants/{restaurant["id"]}/analyze', json={}, headers=headers)
        self.assertEqual(response.status_code, 200)
        AnalysisResultPayload.model_validate(response.json()["result_json"])
        self.assertTrue(response.json()["result_json"]["prioritized_improvements"])
        detail = self.client.get(f'/restaurants/{restaurant["id"]}', headers=headers).json()
        self.assertEqual(detail["latest_analysis"]["id"], response.json()["id"])

    def test_review_body_restaurant_id_must_match_url(self) -> None:
        restaurant = self.restaurant()
        other = self.restaurant(google_place_id="other-place")
        response = self.client.post(f'/restaurants/{restaurant["id"]}/reviews', json=self.review_payload(other["id"]))
        self.assertEqual(response.status_code, 422, "A mismatched URL/body ID must be rejected")

    def test_review_creation_without_body_restaurant_id(self) -> None:
        restaurant = self.restaurant()
        payload = self.review_payload(restaurant["id"])
        payload.pop("restaurant_id")
        response = self.client.post(f'/restaurants/{restaurant["id"]}/reviews', json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["restaurant_id"], restaurant["id"])

    def test_analysis_errors_do_not_expose_internal_details(self) -> None:
        restaurant = self.restaurant()
        sentinel = "private-internal-detail-test-only"
        with patch("app.routers.restaurants.get_or_run_restaurant_analysis", side_effect=RuntimeError(sentinel)):
            response = self.client.post(f'/restaurants/{restaurant["id"]}/analyze')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(sentinel, response.text)
        self.assertEqual(self.client.get("/auth/me/analysis-history").json(), [])

    def test_temporary_database_is_removed_after_fixture_cleanup(self) -> None:
        nested = BackendTestCase()
        nested.setUp()
        try:
            path = nested.database_path
            self.assertTrue(path.exists())
            self.assertEqual(nested.client.get("/restaurants").json(), [])
            nested.tearDown()
        finally:
            nested.doCleanups()
        self.assertFalse(path.exists())
        self.assertEqual(self.client.get("/restaurants").json(), [])

    def test_unmocked_provider_and_network_guards(self) -> None:
        import socket
        with self.assertRaises(AssertionError):
            socket.create_connection(("provider.invalid", 443))
        self.assertEqual(self.unmocked_requests, ["external socket connection"])
        self.unmocked_requests.clear()
        with self.assertRaises(AssertionError):
            socket.getaddrinfo("provider.invalid", 443)
        self.assertEqual(self.unmocked_requests, ["external socket connection"])
        self.unmocked_requests.clear()
        with self.assertRaises(AssertionError):
            self.openai_guard()
        with self.assertRaises(AssertionError):
            self.google_guard("https://provider.invalid")
        self.assertEqual(self.unmocked_requests, ["unmocked provider call", "unmocked provider call"])
        self.unmocked_requests.clear()

    def test_google_provider_response_is_mapped_and_deduplicated(self) -> None:
        target = self.target()
        payload = {"status": "OK", "result": {
            "place_id": target["value"], "name": "Provider Cafe", "formatted_address": "42 Test Road",
            "rating": 4.5, "user_ratings_total": 1,
            "reviews": [{"time": 1577836800, "author_name": "Provider Guest", "rating": 4.0, "text": "Fresh food"}],
        }}
        response = httpx.Response(200, json=payload, request=httpx.Request("GET", "https://provider.invalid"))
        with patch.object(settings, "GOOGLE_PLACES_API_KEY", "test-only-google-key"), patch("app.services.sync.httpx.get", return_value=response) as provider:
            first = self.client.post("/sync/run").json()
            second = self.client.post("/sync/run").json()
        self.assertEqual(first["status"], "COMPLETED")
        self.assertEqual(second["status"], "COMPLETED")
        self.assertEqual(second["reviews_upserted"], 0)
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(self.db.query(Restaurant).one().name, "Provider Cafe")
        review = self.db.query(Review).one()
        self.assertEqual(review.author_name, "Provider Guest")
        self.assertEqual(review.rating, 4.0)

    def test_sync_errors_do_not_expose_keys_or_internal_details(self) -> None:
        self.target()
        sentinel = "private-sync-key-test-only"
        with patch("app.services.sync.run_sync_for_target", side_effect=RuntimeError(sentinel)):
            response = self.client.post("/sync/run")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "FAILED")
        self.assertNotIn(sentinel, response.text)


class TestBadReviewNotifications(BackendTestCase):
    def google_response(self, place_id: str, ratings: list) -> httpx.Response:
        reviews = [{"time": 1577836800 + index, "author_name": f"Guest {index}", "rating": rating,
                    "text": f"Review rated {rating}"} for index, rating in enumerate(ratings)]
        payload = {"status": "OK", "result": {"place_id": place_id, "name": "Provider Cafe",
                                              "formatted_address": "42 Test Road", "rating": 3.5,
                                              "user_ratings_total": len(reviews), "reviews": reviews}}
        return httpx.Response(200, json=payload, request=httpx.Request("GET", "https://provider.invalid"))

    def live_sync(self, ratings: list) -> dict:
        target = self.target()
        with patch.object(settings, "GOOGLE_PLACES_API_KEY", "test-only-google-key"), \
                patch("app.services.sync.httpx.get", return_value=self.google_response(target["value"], ratings)):
            response = self.client.post("/sync/run")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_manual_live_sync_notifies_only_reviews_at_or_below_threshold(self) -> None:
        with self.assertLogs("app.services.notifications", level="WARNING") as logs:
            run = self.live_sync([1.0, 2.0, 3.0, 5.0])
        self.assertEqual(run["status"], "COMPLETED")
        self.assertEqual(run["reviews_upserted"], 4)
        self.assertEqual(len(logs.records), 2)
        rows = self.client.get("/notifications").json()
        for row in rows:
            NotificationResponse.model_validate(row)
        self.assertEqual(sorted(row["review"]["rating"] for row in rows), [1.0, 2.0])
        self.assertTrue(all(row["channel"] == "in_app" and row["status"] == "SENT" for row in rows))
        self.assertTrue(all(row["sync_run_id"] == run["id"] for row in rows))
        restaurant_id = self.db.query(Restaurant).one().id
        self.assertEqual(len(self.client.get(f"/notifications?restaurant_id={restaurant_id}").json()), 2)
        self.assertEqual(self.client.get("/notifications?restaurant_id=999999").json(), [])

    def test_scheduled_sync_entry_point_notifies(self) -> None:
        target = self.target()
        with patch.object(settings, "GOOGLE_PLACES_API_KEY", "test-only-google-key"), \
                patch("app.services.sync.httpx.get", return_value=self.google_response(target["value"], [1.0])):
            run = execute_sync_job(self.db)
        self.assertEqual(run.status, "COMPLETED")
        self.assertEqual(self.db.query(Notification).count(), 1)

    def test_repeated_sync_does_not_duplicate_notifications(self) -> None:
        target = self.target()
        response = self.google_response(target["value"], [1.0, 4.0])
        with patch.object(settings, "GOOGLE_PLACES_API_KEY", "test-only-google-key"), \
                patch("app.services.sync.httpx.get", return_value=response):
            first = self.client.post("/sync/run").json()
            second = self.client.post("/sync/run").json()
        self.assertEqual((first["status"], second["status"]), ("COMPLETED", "COMPLETED"))
        self.assertEqual(second["reviews_upserted"], 0)
        self.assertEqual(self.db.query(Notification).count(), 1)

    def test_mock_sync_never_notifies(self) -> None:
        self.target()
        run = self.client.post("/sync/run").json()
        self.assertEqual(run["status"], "COMPLETED")
        self.assertTrue(self.db.query(Review).filter(Review.rating <= 2.0).count() > 0)
        self.assertEqual(self.db.query(Notification).count(), 0)

    def test_failed_sync_does_not_notify(self) -> None:
        run = self.live_sync([1.0, "not-a-rating"])
        self.assertEqual(run["status"], "FAILED")
        self.assertEqual(self.db.query(Review).count(), 0)
        self.assertEqual(self.db.query(Notification).count(), 0)

    def test_notification_failure_does_not_fail_sync(self) -> None:
        with patch("app.services.notifications.Notification", side_effect=RuntimeError("store down")):
            run = self.live_sync([1.0])
        self.assertEqual(run["status"], "COMPLETED")
        self.assertEqual(self.db.query(Review).count(), 1)
        self.assertEqual(self.db.query(Notification).count(), 0)

    def test_threshold_is_configurable(self) -> None:
        with patch.object(settings, "BAD_REVIEW_RATING_THRESHOLD", 3.0):
            self.live_sync([3.0, 4.0])
        self.assertEqual(self.db.query(Notification).count(), 1)

    def test_notifications_can_be_disabled(self) -> None:
        with patch.object(settings, "BAD_REVIEW_NOTIFICATIONS_ENABLED", False):
            run = self.live_sync([1.0])
        self.assertEqual(run["status"], "COMPLETED")
        self.assertEqual(self.db.query(Notification).count(), 0)


if __name__ == "__main__":
    unittest.main()
