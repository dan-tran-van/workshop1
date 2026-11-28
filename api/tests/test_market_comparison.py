import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

# Support invocation both from the repository root and from api/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import BackendTestCase, settings
from app.models import Review

PASSWORD = "secure-test-password-123"


class MarketComparisonTestCase(BackendTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.resources.enter_context(patch.object(settings, "MIN_REVIEWS_PER_CRITERION", 3))
        self.resources.enter_context(patch.object(settings, "COMPETITOR_MIN_SUGGESTIONS", 5))
        self.resources.enter_context(patch.object(settings, "COMPETITOR_MAX_SUGGESTIONS", 10))
        self.place_counter = 0
        self.review_counter = 0

    def place(self, name: str, user_rating_count: int | None = 100) -> dict:
        self.place_counter += 1
        return self.restaurant(google_place_id=f"place-{self.place_counter}", name=name, user_rating_count=user_rating_count)

    def add_reviews(self, restaurant_id: int, text: str, ratings: list[float]) -> None:
        for rating in ratings:
            self.review_counter += 1
            self.db.add(Review(
                restaurant_id=restaurant_id, author_name="Guest", rating=rating, text=text,
                published_at=datetime(2025, 1, 1) + timedelta(days=self.review_counter),
            ))
        self.db.commit()

    def create_account(self, role: str, email: str, restaurant_ids: list[int] | None = None) -> None:
        response = self.client.post("/admin/users", json={
            "email": email, "full_name": role.title(), "password": PASSWORD,
            "role": role, "restaurant_ids": restaurant_ids or [],
        })
        self.assertEqual(response.status_code, 201, response.text)

    def login_as(self, email: str) -> None:
        response = self.client.post("/auth/login", json={"email": email, "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        self.client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})

    def as_owner_of(self, restaurant_id: int) -> None:
        self.create_account("OWNER", f"owner-{restaurant_id}@example.com", [restaurant_id])
        self.login_as(f"owner-{restaurant_id}@example.com")


class TestCompetitiveSet(MarketComparisonTestCase):
    def test_reviewed_competitors_rank_first_then_closest_google_review_volume(self) -> None:
        own = self.place("Own Kitchen", 500)
        far_reviewed = self.place("Far Reviewed", 100)
        near_reviewed = self.place("Near Reviewed", 480)
        near_unreviewed = self.place("Near Unreviewed", 500)
        far_unreviewed = self.place("Far Unreviewed", 2000)
        self.add_reviews(far_reviewed["id"], "Delicious food", [4.0])
        self.add_reviews(near_reviewed["id"], "Delicious food", [4.0])
        self.as_owner_of(own["id"])

        body = self.client.get(f"/restaurants/{own['id']}/competitors").json()

        self.assertEqual([item["restaurant_id"] for item in body["competitors"]],
                         [near_reviewed["id"], far_reviewed["id"], near_unreviewed["id"], far_unreviewed["id"]])
        first = body["competitors"][0]
        self.assertEqual(first["source"], "SUGGESTED")
        self.assertTrue(first["scorable"])
        self.assertIsNone(first["distance_m"])
        self.assertIsNone(first["cuisine"])
        self.assertIsNone(first["price_level"])
        self.assertTrue(first["reasons"])
        self.assertFalse(body["competitors"][2]["scorable"])
        self.assertTrue(body["can_edit"])
        self.assertTrue(body["data_limitations"])

    def test_fewer_than_minimum_matches_shows_notice_with_found_count(self) -> None:
        own = self.place("Own Kitchen")
        self.place("Only Rival")
        self.as_owner_of(own["id"])

        body = self.client.get(f"/restaurants/{own['id']}/competitors").json()

        self.assertEqual(body["matching_count"], 1)
        self.assertEqual(len(body["competitors"]), 1)
        self.assertIn("Only 1 matching places", body["notice"])
        self.assertIn("expanding the radius", body["notice"])

    def test_suggestions_are_capped_and_pinned_competitor_is_always_kept(self) -> None:
        own = self.place("Own Kitchen", 100)
        rivals = [self.place(f"Rival {index}", 100 + index * 10) for index in range(12)]
        self.as_owner_of(own["id"])
        url = f"/restaurants/{own['id']}/competitors"

        initial = self.client.get(url).json()
        self.assertEqual(len(initial["competitors"]), 10)
        last = rivals[-1]
        self.assertNotIn(last["id"], [item["restaurant_id"] for item in initial["competitors"]])

        pinned = self.client.put(f"{url}/{last['id']}", json={"status": "PINNED"})
        self.assertEqual(pinned.status_code, 200, pinned.text)
        competitors = pinned.json()["competitors"]
        self.assertEqual(len(competitors), 10)
        self.assertEqual((competitors[0]["restaurant_id"], competitors[0]["source"]), (last["id"], "PINNED"))
        self.assertIn("Pinned by you", competitors[0]["reasons"])

        refreshed = self.client.get(url).json()
        self.assertEqual(refreshed["competitors"][0]["restaurant_id"], last["id"])

    def test_dismissed_competitor_is_not_suggested_again_until_restored(self) -> None:
        own = self.place("Own Kitchen")
        rival = self.place("Rival")
        other = self.place("Other")
        self.as_owner_of(own["id"])
        url = f"/restaurants/{own['id']}/competitors"

        dismissed = self.client.put(f"{url}/{rival['id']}", json={"status": "DISMISSED"}).json()
        self.assertEqual([item["restaurant_id"] for item in dismissed["competitors"]], [other["id"]])
        self.assertEqual(dismissed["dismissed"], [{"restaurant_id": rival["id"], "name": "Rival"}])
        self.assertNotIn(rival["id"], [item["restaurant_id"] for item in self.client.get(url).json()["competitors"]])

        restored = self.client.delete(f"{url}/{rival['id']}").json()
        self.assertIn(rival["id"], [item["restaurant_id"] for item in restored["competitors"]])
        self.assertEqual(restored["dismissed"], [])

    def test_manual_competitor_joins_the_set_and_is_scored_like_suggestions(self) -> None:
        own = self.place("Own Kitchen", 100)
        self.place("Close One", 100)
        self.place("Close Two", 110)
        manual = self.place("Far Away", 9000)
        self.add_reviews(manual["id"], "Delicious food", [5.0, 5.0, 5.0])
        self.add_reviews(own["id"], "Delicious food", [3.0, 3.0, 3.0])
        self.as_owner_of(own["id"])
        url = f"/restaurants/{own['id']}/competitors"

        with patch.object(settings, "COMPETITOR_MAX_SUGGESTIONS", 1):
            candidates = self.client.get(f"{url}/candidates?q=far").json()
            self.assertEqual([item["restaurant_id"] for item in candidates], [manual["id"]])
            # Reviewed competitors rank first, so remove it from the suggestion to prove manual adds work.
            self.client.put(f"{url}/{manual['id']}", json={"status": "DISMISSED"})
            added = self.client.put(f"{url}/{manual['id']}", json={"status": "MANUAL"}).json()
            gap = self.client.get(f"{url}/gap").json()

        self.assertEqual(added["competitors"][0]["restaurant_id"], manual["id"])
        self.assertEqual(added["competitors"][0]["source"], "MANUAL")
        self.assertEqual(added["dismissed"], [])
        food = next(row for row in gap["rows"] if row["aspect"] == "food")
        self.assertEqual(food["leader"]["restaurant_id"], manual["id"])
        self.assertEqual(food["status"], "LEARN")

    def test_invalid_selections_are_rejected(self) -> None:
        own = self.place("Own Kitchen")
        self.as_owner_of(own["id"])
        url = f"/restaurants/{own['id']}/competitors"

        self.assertEqual(self.client.put(f"{url}/{own['id']}", json={"status": "PINNED"}).status_code, 422)
        self.assertEqual(self.client.put(f"{url}/999", json={"status": "PINNED"}).status_code, 404)
        self.assertEqual(self.client.put(f"{url}/999", json={"status": "SUGGESTED"}).status_code, 422)


class TestMarketComparisonAccess(MarketComparisonTestCase):
    def test_role_rules(self) -> None:
        own = self.place("Own Kitchen")
        rival = self.place("Rival")
        url = f"/restaurants/{own['id']}/competitors"
        self.create_account("OWNER", "owner@example.com", [own["id"]])
        self.create_account("ANALYST", "analyst@example.com")

        # Admins do not use market comparison.
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(f"{url}/gap").status_code, 403)

        self.login_as("analyst@example.com")
        view = self.client.get(url)
        self.assertEqual(view.status_code, 200)
        self.assertFalse(view.json()["can_edit"])
        self.assertEqual(self.client.get(f"{url}/gap").status_code, 200)
        self.assertEqual(self.client.put(f"{url}/{rival['id']}", json={"status": "PINNED"}).status_code, 403)
        self.assertEqual(self.client.delete(f"{url}/{rival['id']}").status_code, 403)
        self.assertEqual(self.client.get(f"{url}/candidates").status_code, 403)

        self.login_as("owner@example.com")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(f"/restaurants/{rival['id']}/competitors").status_code, 404)
        self.assertEqual(self.client.put(f"/restaurants/{rival['id']}/competitors/{own['id']}", json={"status": "PINNED"}).status_code, 404)


class TestCriteriaGap(MarketComparisonTestCase):
    def build_market(self) -> tuple[dict, dict, dict]:
        own = self.place("Own Kitchen")
        strong = self.place("Strong Rival")
        steady = self.place("Steady Rival")
        thin = self.place("Thin Rival")
        # food: own 3.0 vs avg(5.0, 4.0) = 4.5 -> LEARN. Thin Rival has only 2 mentions and is excluded.
        self.add_reviews(own["id"], "Delicious food", [3.0, 3.0, 3.0])
        self.add_reviews(strong["id"], "Delicious food", [5.0, 5.0, 5.0])
        self.add_reviews(steady["id"], "Delicious food", [4.0, 4.0, 4.0])
        self.add_reviews(thin["id"], "Delicious food", [1.0, 1.0])
        # service: own 5.0 vs avg(2.0, 3.0) = 2.5 < 3.5 -> ATTACK.
        self.add_reviews(own["id"], "Rude staff", [5.0, 5.0, 5.0])
        self.add_reviews(strong["id"], "Rude staff", [2.0, 2.0, 2.0])
        self.add_reviews(steady["id"], "Rude staff", [3.0, 3.0, 3.0])
        # ambience: own 4.0 vs avg 4.0 -> KEEP.
        self.add_reviews(own["id"], "Cozy decor", [4.0, 4.0, 4.0])
        self.add_reviews(strong["id"], "Cozy decor", [4.0, 4.0, 4.0])
        # price: own has only one mention -> not enough data.
        self.add_reviews(own["id"], "Fair price", [4.0])
        self.add_reviews(strong["id"], "Fair price", [4.0, 4.0, 4.0])
        # hygiene: no competitor reaches the threshold -> not enough data.
        self.add_reviews(own["id"], "Very clean", [4.0, 4.0, 4.0])
        return own, strong, steady

    def rows(self, own_id: int) -> dict:
        response = self.client.get(f"/restaurants/{own_id}/competitors/gap")
        self.assertEqual(response.status_code, 200, response.text)
        return {row["aspect"]: row for row in response.json()["rows"]}

    def test_gap_table_scores_labels_and_leader(self) -> None:
        own, strong, _ = self.build_market()
        self.as_owner_of(own["id"])
        rows = self.rows(own["id"])

        self.assertEqual(list(rows), ["food", "service", "wait_time", "hygiene", "ambience", "price"])
        food = rows["food"]
        self.assertEqual((food["own_score"], food["competitor_avg"], food["competitors_scored"]), (3.0, 4.5, 2))
        self.assertEqual((food["gap_vs_avg"], food["gap_vs_leader"], food["status"]), (-1.5, -2.0, "LEARN"))
        self.assertEqual(food["leader"], {"restaurant_id": strong["id"], "name": "Strong Rival", "score": 5.0})
        self.assertEqual((rows["service"]["gap_vs_avg"], rows["service"]["status"]), (2.5, "ATTACK"))
        self.assertEqual((rows["ambience"]["gap_vs_avg"], rows["ambience"]["status"]), (0.0, "KEEP"))

    def test_criteria_below_threshold_show_not_enough_data(self) -> None:
        own, _, _ = self.build_market()
        self.as_owner_of(own["id"])
        rows = self.rows(own["id"])

        price = rows["price"]
        self.assertEqual(price["status"], "INSUFFICIENT_DATA")
        self.assertIsNone(price["gap_vs_avg"])
        self.assertIn("1 of your reviews", price["insufficient_reason"])
        self.assertEqual(rows["hygiene"]["status"], "INSUFFICIENT_DATA")
        self.assertIn("no competitor", rows["hygiene"]["insufficient_reason"])
        self.assertEqual(rows["wait_time"]["status"], "INSUFFICIENT_DATA")

        explain = self.client.post(f"/restaurants/{own['id']}/competitors/gap/price/explain")
        self.assertEqual(explain.status_code, 422)
        self.assertIn("Not enough data", explain.json()["detail"])
        self.assertEqual(self.client.post(f"/restaurants/{own['id']}/competitors/gap/parking/explain").status_code, 404)

    def test_heuristic_explanation_cites_real_reviews_from_both_sides(self) -> None:
        own, strong, _ = self.build_market()
        self.as_owner_of(own["id"])

        response = self.client.post(f"/restaurants/{own['id']}/competitors/gap/food/explain")

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body["status"], body["model"]), ("LEARN", "heuristic"))
        self.assertIn("Strong Rival", body["explanation"])
        self.assertTrue(2 <= len(body["evidence"]) <= 3)
        self.assertEqual(body["evidence"][0]["restaurant_id"], strong["id"])
        self.assertTrue(any(item["is_own"] for item in body["evidence"]))
        stored_ids = {review.id for review in self.db.query(Review).all()}
        self.assertTrue(all(item["review_id"] in stored_ids for item in body["evidence"]))
        self.assertTrue(all(item["text"] == "Delicious food" for item in body["evidence"]))

    def test_analyst_can_view_explanations(self) -> None:
        own, _, _ = self.build_market()
        self.create_account("ANALYST", "analyst@example.com")
        self.login_as("analyst@example.com")

        response = self.client.post(f"/restaurants/{own['id']}/competitors/gap/service/explain")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ATTACK")

    def test_openai_explanation_uses_only_provided_review_ids(self) -> None:
        own, strong, _ = self.build_market()
        self.as_owner_of(own["id"])
        strong_review = self.db.query(Review).filter(Review.restaurant_id == strong["id"], Review.text == "Delicious food").first()
        own_review = self.db.query(Review).filter(Review.restaurant_id == own["id"], Review.text == "Delicious food").first()
        content = json.dumps({"explanation": "Guests praise Strong Rival's food more.",
                              "evidence_review_ids": [strong_review.id, own_review.id]})

        with self.openai_response(content) as completion:
            body = self.client.post(f"/restaurants/{own['id']}/competitors/gap/food/explain").json()

        completion.assert_called_once()
        self.assertEqual(body["explanation"], "Guests praise Strong Rival's food more.")
        self.assertEqual([item["review_id"] for item in body["evidence"]], [strong_review.id, own_review.id])
        self.assertEqual(body["model"], settings.OPENAI_MODEL)

    def test_openai_answer_citing_unknown_reviews_falls_back_to_heuristic(self) -> None:
        own, _, _ = self.build_market()
        self.as_owner_of(own["id"])
        content = json.dumps({"explanation": "Invented claim.", "evidence_review_ids": [99999]})

        with self.openai_response(content):
            body = self.client.post(f"/restaurants/{own['id']}/competitors/gap/food/explain").json()

        self.assertEqual(body["model"], "heuristic-fallback")
        self.assertNotEqual(body["explanation"], "Invented claim.")
        self.assertTrue(2 <= len(body["evidence"]) <= 3)


if __name__ == "__main__":
    unittest.main()
