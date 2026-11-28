import sys
import unittest
from pathlib import Path

# Support invocation both from the repository root and from api/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import BackendTestCase
from app.models import Review, ReviewEmbedding
from app.services.vector_store import search_similar_reviews, store_review_embedding


class VectorStoreTestCase(BackendTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.restaurant_a = self.restaurant(google_place_id="vector-place-a", name="Place A")
        self.restaurant_b = self.restaurant(google_place_id="vector-place-b", name="Place B")

    def test_upsert_and_cosine_retrieval_are_persisted_and_ranked(self) -> None:
        first = self.review(self.restaurant_a["id"], text="Great food")
        second = self.review(self.restaurant_a["id"], text="Slow service")
        unrelated = self.review(self.restaurant_b["id"], text="Good ambience")

        stored = store_review_embedding(self.db, first["id"], [1, 0], "test-model")
        store_review_embedding(self.db, first["id"], [0.8, 0.2], "test-model")
        store_review_embedding(self.db, second["id"], [0, 1], "test-model")
        store_review_embedding(self.db, unrelated["id"], [1, 0], "another-model")

        self.assertEqual(self.db.query(ReviewEmbedding).count(), 3)
        self.assertEqual(stored.dimensions, 2)
        results = search_similar_reviews(self.db, [1, 0], "test-model", limit=5)

        self.assertEqual([item.review.id for item in results], [first["id"], second["id"]])
        self.assertAlmostEqual(results[0].similarity, 0.8 / (0.8**2 + 0.2**2) ** 0.5)
        self.assertAlmostEqual(results[1].similarity, 0.0)

    def test_retrieval_can_be_scoped_thresholded_and_ignores_stale_text(self) -> None:
        own = self.review(self.restaurant_a["id"], text="Fresh dishes")
        other = self.review(self.restaurant_b["id"], text="Fresh dishes nearby")
        store_review_embedding(self.db, own["id"], [1, 0], "test-model")
        store_review_embedding(self.db, other["id"], [0.7, 0.3], "test-model")

        scoped = search_similar_reviews(self.db, [1, 0], "test-model", restaurant_ids=[self.restaurant_b["id"]])
        self.assertEqual([item.review.id for item in scoped], [other["id"]])
        self.assertGreater(scoped[0].similarity, 0.8)
        filtered = search_similar_reviews(
            self.db, [1, 0], "test-model", restaurant_ids=[self.restaurant_b["id"]], min_similarity=0.95
        )
        self.assertEqual(filtered, [])

        self.db.query(Review).filter_by(id=own["id"]).update({"text": "Updated review text"})
        self.db.commit()
        results = search_similar_reviews(self.db, [1, 0], "test-model", restaurant_ids=[self.restaurant_a["id"]])
        self.assertEqual(results, [])

    def test_invalid_vectors_and_search_arguments_are_rejected(self) -> None:
        review = self.review(self.restaurant_a["id"])
        for vector in ([], [0.0, 0.0], [1.0, float("nan")], [True, 1.0]):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                store_review_embedding(self.db, review["id"], vector, "test-model")

        store_review_embedding(self.db, review["id"], [1, 0], "test-model")
        with self.assertRaises(ValueError):
            search_similar_reviews(self.db, [1, 0], "test-model", limit=0)
        with self.assertRaises(ValueError):
            search_similar_reviews(self.db, [1, 0], "test-model", min_similarity=1.1)
        with self.assertRaises(ValueError):
            store_review_embedding(self.db, review["id"], [1, 0, 0], "test-model")


if __name__ == "__main__":
    unittest.main()
