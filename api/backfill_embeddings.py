"""Backfill review embeddings for existing restaurants in the database."""

import argparse
import os
import sys
from typing import List, Optional, Sequence

# Add api directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Restaurant, Review
from app.services.vector_store import ensure_restaurant_embeddings, ensure_review_embeddings


def backfill_embeddings(
    db: Session,
    restaurant_ids: Optional[Sequence[int]] = None,
    review_ids: Optional[Sequence[int]] = None,
    model: Optional[str] = None,
    batch_size: int = 100,
) -> int:
    """Index unembedded or stale reviews for the requested restaurants, reviews, or all restaurants."""
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured; cannot generate embeddings.")

    target_review_ids: List[int] = []
    if restaurant_ids is None and review_ids is None:
        all_restaurant_ids = [row.id for row in db.query(Restaurant.id).order_by(Restaurant.id.asc()).all()]
        if not all_restaurant_ids:
            return 0
        return ensure_restaurant_embeddings(db, all_restaurant_ids, model=model, batch_size=batch_size)

    if restaurant_ids:
        rows = (
            db.query(Review.id)
            .filter(Review.restaurant_id.in_(list(dict.fromkeys(restaurant_ids))))
            .order_by(Review.id.asc())
            .all()
        )
        target_review_ids.extend(row.id for row in rows)
    if review_ids:
        target_review_ids.extend(review_ids)

    deduped_review_ids = list(dict.fromkeys(target_review_ids))
    if not deduped_review_ids:
        return 0
    return ensure_review_embeddings(db, deduped_review_ids, model=model, batch_size=batch_size)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill review embeddings for existing restaurants or reviews.")
    parser.add_argument(
        "--restaurant-id",
        type=int,
        action="append",
        dest="restaurant_ids",
        help="Optional restaurant ID to backfill all its reviews (repeatable).",
    )
    parser.add_argument(
        "--review-id",
        type=int,
        action="append",
        dest="review_ids",
        help="Optional review ID to backfill (repeatable; can be combined with --restaurant-id).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Embedding model name (defaults to {settings.OPENAI_EMBEDDING_MODEL}).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of reviews to embed per API batch (default: 100).",
    )
    args = parser.parse_args(argv)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        model_name = args.model or settings.OPENAI_EMBEDDING_MODEL
        count = backfill_embeddings(
            db,
            restaurant_ids=args.restaurant_ids,
            review_ids=args.review_ids,
            model=model_name,
            batch_size=args.batch_size,
        )
        print(f"Embedded {count} review(s) using model '{model_name}'.")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
