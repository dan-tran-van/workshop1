import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Support invocation both from the repository root and from api/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import BackendTestCase, settings
from app.models import Review, ReviewEmbedding
from backfill_embeddings import backfill_embeddings
from app.services.vector_store import (
    ensure_restaurant_embeddings,
    rank_restaurants_by_embedding_similarity,
    search_similar_reviews,
    store_review_embedding,
)


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

    def test_restaurant_centroid_similarity_and_ensure_embeddings(self) -> None:
        r1 = self.review(self.restaurant_a["id"], text="Great ramen")
        r2 = self.review(self.restaurant_b["id"], text="Rich broth")
        c = self.restaurant(google_place_id="vector-place-c", name="Place C")
        r3 = self.review(c["id"], text="Sweet pastries")

        # Without API key, ensure_restaurant_embeddings is a safe no-op.
        with patch.object(settings, "OPENAI_API_KEY", ""):
            self.assertEqual(ensure_restaurant_embeddings(self.db, [self.restaurant_a["id"]]), 0)

        # With API key, only missing/stale reviews are embedded.
        with patch.object(settings, "OPENAI_API_KEY", "test-key"), patch(
            "app.services.vector_store.embed_texts",
            side_effect=[[[1.0, 0.0]], [[0.9, 0.1], [0.0, 1.0]]],
        ) as mocked_embed:
            self.assertEqual(ensure_restaurant_embeddings(self.db, [self.restaurant_a["id"]], model="test-model"), 1)
            self.assertEqual(ensure_restaurant_embeddings(self.db, [self.restaurant_a["id"]], model="test-model"), 0)
            self.assertEqual(
                ensure_restaurant_embeddings(
                    self.db, [self.restaurant_b["id"], c["id"]], model="test-model"
                ),
                2,
            )
            self.assertEqual(mocked_embed.call_count, 2)

        scores = rank_restaurants_by_embedding_similarity(
            self.db, self.restaurant_a["id"], [self.restaurant_b["id"], c["id"]], model="test-model"
        )
        self.assertGreater(scores[self.restaurant_b["id"]], 0.99)
        self.assertAlmostEqual(scores[c["id"]], 0.0)

        # Stale review text excludes the outdated embedding from centroid ranking.
        self.db.query(Review).filter_by(id=r2["id"]).update({"text": "Changed text"})
        self.db.commit()
        updated_scores = rank_restaurants_by_embedding_similarity(
            self.db, self.restaurant_a["id"], [self.restaurant_b["id"], c["id"]], model="test-model"
        )
        self.assertNotIn(self.restaurant_b["id"], updated_scores)
        self.assertIn(c["id"], updated_scores)

    def test_backfill_embeddings_script_handles_missing_key_and_targets(self) -> None:
        rev_a = self.review(self.restaurant_a["id"], text="Crispy duck")
        rev_b = self.review(self.restaurant_b["id"], text="Matcha latte")

        with patch.object(settings, "OPENAI_API_KEY", ""):
            with self.assertRaises(RuntimeError):
                backfill_embeddings(self.db)

        # Backfill only a specific review ID.
        with patch.object(settings, "OPENAI_API_KEY", "test-key"), patch(
            "app.services.vector_store.embed_texts",
            return_value=[[1.0, 0.0]],
        ):
            self.assertEqual(backfill_embeddings(self.db, review_ids=[rev_a["id"]], model="test-model"), 1)
        self.assertEqual(self.db.query(ReviewEmbedding).count(), 1)

        # Backfill a restaurant + review ID together (already-indexed review is skipped).
        with patch.object(settings, "OPENAI_API_KEY", "test-key"), patch(
            "app.services.vector_store.embed_texts",
            return_value=[[0.0, 1.0]],
        ):
            self.assertEqual(
                backfill_embeddings(
                    self.db,
                    restaurant_ids=[self.restaurant_b["id"]],
                    review_ids=[rev_a["id"], rev_b["id"]],
                    model="test-model",
                ),
                1,
            )
        self.assertEqual(self.db.query(ReviewEmbedding).count(), 2)


if __name__ == "__main__":
    unittest.main()
