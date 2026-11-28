"""Database-backed storage and similarity retrieval for review embeddings."""

import hashlib
import math
from dataclasses import dataclass
from numbers import Real
from typing import List, Optional, Sequence

from sqlalchemy.orm import Session

from app.models import Review, ReviewEmbedding


@dataclass(frozen=True)
class SimilarReview:
    review: Review
    similarity: float


def _validated_vector(vector: Sequence[Real]) -> List[float]:
    if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence) or not vector:
        raise ValueError("An embedding must be a non-empty numeric sequence")

    normalized: List[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("Embedding values must be finite numbers")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Embedding values must be finite numbers")
        normalized.append(number)

    if not any(value != 0.0 for value in normalized):
        raise ValueError("An embedding must have a non-zero magnitude")
    return normalized


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def store_review_embedding(
    db: Session,
    review_id: int,
    embedding: Sequence[Real],
    model: str,
) -> ReviewEmbedding:
    """Insert or replace a review's vector for a particular embedding model."""
    vector = _validated_vector(embedding)
    model_name = model.strip() if isinstance(model, str) else ""
    if not model_name:
        raise ValueError("An embedding model name is required")

    review = db.query(Review).filter(Review.id == review_id).first()
    if review is None:
        raise LookupError(f"Review {review_id} does not exist")

    model_dimensions = (
        db.query(ReviewEmbedding.dimensions)
        .filter(ReviewEmbedding.model == model_name)
        .first()
    )
    if model_dimensions is not None and model_dimensions[0] != len(vector):
        raise ValueError("Embedding dimensions must match the dimensions already stored for this model")

    row = (
        db.query(ReviewEmbedding)
        .filter(ReviewEmbedding.review_id == review_id, ReviewEmbedding.model == model_name)
        .first()
    )
    if row is None:
        row = ReviewEmbedding(review_id=review_id, model=model_name)
        db.add(row)

    row.embedding = vector
    row.dimensions = len(vector)
    row.content_hash = _content_hash(review.text)
    db.commit()
    db.refresh(row)
    return row


def search_similar_reviews(
    db: Session,
    query_embedding: Sequence[Real],
    model: str,
    restaurant_ids: Optional[Sequence[int]] = None,
    limit: int = 10,
    min_similarity: Optional[float] = None,
) -> List[SimilarReview]:
    """Return matching stored reviews ranked by cosine similarity, highest first."""
    query_vector = _validated_vector(query_embedding)
    model_name = model.strip() if isinstance(model, str) else ""
    if not model_name:
        raise ValueError("An embedding model name is required")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("Limit must be a positive integer")
    if min_similarity is not None and (
        isinstance(min_similarity, bool)
        or not isinstance(min_similarity, Real)
        or not math.isfinite(float(min_similarity))
        or not -1.0 <= float(min_similarity) <= 1.0
    ):
        raise ValueError("Minimum similarity must be between -1 and 1")
    if restaurant_ids is not None and not restaurant_ids:
        return []

    query_norm = math.sqrt(sum(value * value for value in query_vector))
    rows = (
        db.query(ReviewEmbedding, Review)
        .join(Review, Review.id == ReviewEmbedding.review_id)
        .filter(
            ReviewEmbedding.model == model_name,
            ReviewEmbedding.dimensions == len(query_vector),
        )
    )
    if restaurant_ids is not None:
        rows = rows.filter(Review.restaurant_id.in_(restaurant_ids))

    matches: List[SimilarReview] = []
    for stored, review in rows.all():
        if stored.content_hash != _content_hash(review.text):
            continue
        vector = _validated_vector(stored.embedding)
        vector_norm = math.sqrt(sum(value * value for value in vector))
        score = sum(left * right for left, right in zip(query_vector, vector)) / (query_norm * vector_norm)
        score = max(-1.0, min(1.0, score))
        if min_similarity is None or score >= float(min_similarity):
            matches.append(SimilarReview(review=review, similarity=score))

    matches.sort(key=lambda match: (-match.similarity, match.review.id))
    return matches[:limit]
