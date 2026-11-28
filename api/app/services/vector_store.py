"""Database-backed storage and similarity retrieval for review embeddings."""

import hashlib
import logging
import math
from dataclasses import dataclass
from numbers import Real
from typing import Any, Dict, List, Optional, Sequence

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Restaurant, Review, ReviewEmbedding

logger = logging.getLogger(__name__)


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


def _unit_normalize(vector: Sequence[float]) -> Optional[List[float]]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0 or not math.isfinite(norm):
        return None
    return [value / norm for value in vector]


def embed_texts(texts: Sequence[str], model: Optional[str] = None) -> List[List[float]]:
    """Generate embedding vectors via OpenAI; returns [] when unconfigured or on failure."""
    if not settings.OPENAI_API_KEY or not texts:
        return []
    cleaned = [text.strip() for text in texts]
    if any(not text for text in cleaned):
        raise ValueError("Texts to embed must be non-empty")

    model_name = (model or settings.OPENAI_EMBEDDING_MODEL).strip()
    if not model_name:
        raise ValueError("An embedding model name is required")

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.embeddings.create(model=model_name, input=cleaned)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [_validated_vector(item.embedding) for item in ordered]
    except Exception as exc:
        logger.warning(f"Embedding generation failed for model '{model_name}': {exc}")
        return []


def _index_reviews(
    db: Session,
    reviews: Sequence[Review],
    model: Optional[str] = None,
    batch_size: int = 100,
) -> int:
    """Index any unembedded or stale reviews in the given sequence."""
    if not settings.OPENAI_API_KEY or not reviews:
        return 0

    model_name = (model or settings.OPENAI_EMBEDDING_MODEL).strip()
    if not model_name:
        return 0

    existing = {
        row.review_id: row.content_hash
        for row in db.query(ReviewEmbedding.review_id, ReviewEmbedding.content_hash)
        .filter(
            ReviewEmbedding.model == model_name,
            ReviewEmbedding.review_id.in_([review.id for review in reviews]),
        )
        .all()
    }
    pending = [
        review
        for review in reviews
        if review.text and review.text.strip() and existing.get(review.id) != _content_hash(review.text)
    ]
    if not pending:
        return 0

    stored_count = 0
    for start in range(0, len(pending), batch_size):
        chunk = pending[start : start + batch_size]
        vectors = embed_texts([review.text for review in chunk], model=model_name)
        if len(vectors) != len(chunk):
            break
        for review, vector in zip(chunk, vectors):
            store_review_embedding(db, review.id, vector, model_name)
            stored_count += 1
    return stored_count


def ensure_review_embeddings(
    db: Session,
    review_ids: Sequence[int],
    model: Optional[str] = None,
    batch_size: int = 100,
) -> int:
    """Index any unembedded or stale reviews for the given review IDs when an API key is set."""
    if not settings.OPENAI_API_KEY or not review_ids:
        return 0
    reviews = (
        db.query(Review)
        .filter(Review.id.in_(review_ids))
        .order_by(Review.id.asc())
        .all()
    )
    return _index_reviews(db, reviews, model=model, batch_size=batch_size)


def ensure_restaurant_embeddings(
    db: Session,
    restaurant_ids: Sequence[int],
    model: Optional[str] = None,
    batch_size: int = 100,
) -> int:
    """Index any unembedded or stale reviews for the given restaurants when an API key is set."""
    if not settings.OPENAI_API_KEY or not restaurant_ids:
        return 0
    reviews = (
        db.query(Review)
        .filter(Review.restaurant_id.in_(restaurant_ids))
        .order_by(Review.id.asc())
        .all()
    )
    return _index_reviews(db, reviews, model=model, batch_size=batch_size)


def compute_restaurant_centroids(
    db: Session,
    restaurant_ids: Sequence[int],
    model: Optional[str] = None,
) -> Dict[int, List[float]]:
    """Compute a unit-normalized centroid vector per restaurant from its fresh review embeddings."""
    if not restaurant_ids:
        return {}
    model_name = (model or settings.OPENAI_EMBEDDING_MODEL).strip()
    if not model_name:
        return {}

    rows = (
        db.query(Review.restaurant_id, Review.text, ReviewEmbedding.embedding, ReviewEmbedding.content_hash)
        .join(Review, Review.id == ReviewEmbedding.review_id)
        .filter(
            Review.restaurant_id.in_(restaurant_ids),
            ReviewEmbedding.model == model_name,
        )
        .all()
    )

    accumulators: Dict[int, List[float]] = {}
    dimensions: Dict[int, int] = {}
    for restaurant_id, text, raw_embedding, content_hash in rows:
        if content_hash != _content_hash(text):
            continue
        unit_vec = _unit_normalize(_validated_vector(raw_embedding))
        if unit_vec is None:
            continue
        if restaurant_id not in accumulators:
            accumulators[restaurant_id] = list(unit_vec)
            dimensions[restaurant_id] = len(unit_vec)
        elif dimensions[restaurant_id] == len(unit_vec):
            acc = accumulators[restaurant_id]
            for idx, value in enumerate(unit_vec):
                acc[idx] += value

    centroids: Dict[int, List[float]] = {}
    for restaurant_id, summed in accumulators.items():
        centroid = _unit_normalize(summed)
        if centroid is not None:
            centroids[restaurant_id] = centroid
    return centroids


def rank_restaurants_by_embedding_similarity(
    db: Session,
    source_restaurant_id: int,
    candidate_ids: Sequence[int],
    model: Optional[str] = None,
) -> Dict[int, float]:
    """Return cosine similarity scores between source_restaurant_id and candidates with embeddings."""
    unique_candidates = [cid for cid in dict.fromkeys(candidate_ids) if cid != source_restaurant_id]
    if not unique_candidates:
        return {}

    centroids = compute_restaurant_centroids(db, [source_restaurant_id, *unique_candidates], model=model)
    source_centroid = centroids.get(source_restaurant_id)
    if source_centroid is None:
        return {}

    scores: Dict[int, float] = {}
    for candidate_id in unique_candidates:
        candidate_centroid = centroids.get(candidate_id)
        if candidate_centroid is None or len(candidate_centroid) != len(source_centroid):
            continue
        score = sum(left * right for left, right in zip(source_centroid, candidate_centroid))
        scores[candidate_id] = max(-1.0, min(1.0, score))
    return scores


def search_reviews(
    db: Session,
    query: str,
    restaurant_ids: Optional[Sequence[int]] = None,
    limit: int = 10,
    min_similarity: Optional[float] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Search reviews semantically via embeddings, falling back to SQL ILIKE when unavailable."""
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Search query must be non-empty")

    if restaurant_ids is not None and not restaurant_ids:
        return {"query": cleaned, "mode": "semantic", "model": None, "results": []}

    model_name = (model or settings.OPENAI_EMBEDDING_MODEL).strip()
    query_vectors = embed_texts([cleaned], model=model_name) if model_name else []

    if query_vectors:
        has_embeddings_query = db.query(ReviewEmbedding.id).join(
            Review, Review.id == ReviewEmbedding.review_id
        ).filter(ReviewEmbedding.model == model_name)
        if restaurant_ids is not None:
            has_embeddings_query = has_embeddings_query.filter(Review.restaurant_id.in_(restaurant_ids))

        if has_embeddings_query.first() is not None:
            matches = search_similar_reviews(
                db,
                query_vectors[0],
                model=model_name,
                restaurant_ids=restaurant_ids,
                limit=limit,
                min_similarity=min_similarity,
            )
            restaurant_names = {
                row.id: row.name
                for row in db.query(Restaurant.id, Restaurant.name)
                .filter(Restaurant.id.in_([match.review.restaurant_id for match in matches]))
                .all()
            } if matches else {}
            return {
                "query": cleaned,
                "mode": "semantic",
                "model": model_name,
                "results": [
                    {
                        "id": match.review.id,
                        "restaurant_id": match.review.restaurant_id,
                        "restaurant_name": restaurant_names.get(match.review.restaurant_id, ""),
                        "author_name": match.review.author_name,
                        "author_uri": match.review.author_uri,
                        "rating": match.review.rating,
                        "text": match.review.text,
                        "published_at": match.review.published_at,
                        "external_review_id": match.review.external_review_id,
                        "similarity": round(match.similarity, 4),
                        "match_type": "semantic",
                    }
                    for match in matches
                ],
            }

    keyword_query = (
        db.query(Review, Restaurant.name)
        .join(Restaurant, Restaurant.id == Review.restaurant_id)
        .filter(Review.text.ilike(f"%{cleaned}%"))
    )
    if restaurant_ids is not None:
        keyword_query = keyword_query.filter(Review.restaurant_id.in_(restaurant_ids))
    rows = keyword_query.order_by(Review.published_at.desc(), Review.id.desc()).limit(limit).all()

    return {
        "query": cleaned,
        "mode": "keyword_fallback",
        "model": None,
        "results": [
            {
                "id": review.id,
                "restaurant_id": review.restaurant_id,
                "restaurant_name": restaurant_name,
                "author_name": review.author_name,
                "author_uri": review.author_uri,
                "rating": review.rating,
                "text": review.text,
                "published_at": review.published_at,
                "external_review_id": review.external_review_id,
                "similarity": None,
                "match_type": "keyword",
            }
            for review, restaurant_name in rows
        ],
    }
