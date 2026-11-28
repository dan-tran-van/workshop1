import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Add api directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app.models import Restaurant, Review, SyncTarget
from app.services.analysis import get_or_run_restaurant_analysis


DATASETS: List[str] = [
    "district2_restaurants_reviews",
    "alaska_moose_tooth_reviews",
    "district1_restaurants_reviews",
    "austin_bbq_reviews",
]


def find_data_file(dataset: str) -> Optional[str]:
    """Find a dump file for one dataset from candidate paths."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    names = [f"{dataset}.json", f"{dataset} 1.json"]
    candidates = [os.path.join(base_dir, n) for n in names]
    candidates += [os.path.join(base_dir, "..", n) for n in names]
    candidates += names
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def find_data_files() -> List[str]:
    """Find every known dump file; at least one must exist."""
    found = [path for path in (find_data_file(d) for d in DATASETS) if path]
    if not found:
        raise FileNotFoundError(
            f"Could not find any data dump file. Expected one of: {[d + '.json' for d in DATASETS]}"
        )
    return found


def load_dump(db: Session, data_file: str, source_id_to_restaurant: Dict[str, Restaurant]) -> None:
    """Upsert the restaurants and reviews from one JSON dump."""
    print(f"Loading data dump from: {data_file}")
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    restaurants_data = data.get("restaurants", [])
    reviews_data = data.get("reviews", [])

    print(f"Upserting {len(restaurants_data)} restaurants...")
    restaurants_upserted = 0

    for r_data in restaurants_data:
        place_id = r_data["google_place_id"]
        last_synced = (
            datetime.fromisoformat(r_data["last_synced_at"])
            if r_data.get("last_synced_at")
            else None
        )
        updated = (
            datetime.fromisoformat(r_data["updated_at"])
            if r_data.get("updated_at")
            else None
        )

        restaurant = db.query(Restaurant).filter(Restaurant.google_place_id == place_id).first()
        if restaurant:
            restaurant.name = r_data["name"]
            restaurant.address = r_data.get("address")
            restaurant.google_rating = r_data.get("google_rating")
            restaurant.user_rating_count = r_data.get("user_rating_count")
            restaurant.last_synced_at = last_synced
            restaurant.updated_at = updated
        else:
            restaurant = Restaurant(
                google_place_id=place_id,
                name=r_data["name"],
                address=r_data.get("address"),
                google_rating=r_data.get("google_rating"),
                user_rating_count=r_data.get("user_rating_count"),
                last_synced_at=last_synced,
                updated_at=updated,
            )
            db.add(restaurant)
            restaurants_upserted += 1

        db.flush()
        source_id_to_restaurant[r_data["source_id"]] = restaurant

    print(f"Restaurants processed: {len(restaurants_data)} ({restaurants_upserted} new)")

    print(f"Upserting {len(reviews_data)} reviews...")
    reviews_upserted = 0
    now = datetime.now(timezone.utc)

    for rev_data in reviews_data:
        rest = source_id_to_restaurant.get(rev_data["restaurant_source_id"])
        if not rest:
            continue

        ext_id = rev_data.get("external_review_id") or rev_data.get("source_id")
        pub_at = (
            datetime.fromisoformat(rev_data["published_at"])
            if rev_data.get("published_at")
            else now
        )
        rating_val = float(
            rev_data.get("rating")
            if rev_data.get("rating") is not None
            else (rest.google_rating or 5.0)
        )

        review = db.query(Review).filter(Review.external_review_id == ext_id).first()
        if review:
            review.restaurant_id = rest.id
            review.author_name = rev_data.get("author_name", "Anonymous")
            review.author_uri = rev_data.get("author_uri")
            review.rating = rating_val
            review.text = rev_data.get("text", "")
            review.published_at = pub_at
        else:
            review = Review(
                restaurant_id=rest.id,
                external_review_id=ext_id,
                author_name=rev_data.get("author_name", "Anonymous"),
                author_uri=rev_data.get("author_uri"),
                rating=rating_val,
                text=rev_data.get("text", ""),
                published_at=pub_at,
            )
            db.add(review)
            reviews_upserted += 1

    print(f"Reviews processed: {len(reviews_data)} ({reviews_upserted} new)")


def seed_data(reset: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if reset or "--reset" in sys.argv or "-r" in sys.argv:
        print("Resetting existing database data...")
        db.query(SyncTarget).delete()
        db.query(Restaurant).delete()
        db.commit()

    # Clean up legacy dummy placeholder restaurants if present
    legacy_ids = ["ChIJ_golden_lotus_001", "ChIJ_sakura_ramen_002"]
    legacy_count = (
        db.query(Restaurant)
        .filter(Restaurant.google_place_id.in_(legacy_ids))
        .delete(synchronize_session=False)
    )
    if legacy_count > 0:
        print(f"Removed {legacy_count} legacy dummy restaurant(s).")
        db.commit()

    source_id_to_restaurant: Dict[str, Restaurant] = {}
    for data_file in find_data_files():
        load_dump(db, data_file, source_id_to_restaurant)

    print("Configuring sync targets...")
    targets_added = 0
    for rest in source_id_to_restaurant.values():
        # Only add valid place IDs to sync targets (omit pending placeholders)
        if not rest.google_place_id.startswith("pending:"):
            existing_target = (
                db.query(SyncTarget)
                .filter(
                    SyncTarget.target_type == "place_id",
                    SyncTarget.value == rest.google_place_id,
                )
                .first()
            )
            if not existing_target:
                db.add(
                    SyncTarget(
                        target_type="place_id",
                        value=rest.google_place_id,
                        language_code="en",
                        is_active=True,
                        last_synced_at=rest.last_synced_at,
                    )
                )
                targets_added += 1

    db.commit()
    print(f"Sync targets configured: {targets_added} new")

    # Generate initial cached analysis for first restaurant with reviews
    sample_restaurant = (
        db.query(Restaurant)
        .join(Review, Restaurant.id == Review.restaurant_id)
        .first()
    )
    if sample_restaurant:
        print(f"Generating initial cached analysis for '{sample_restaurant.name}'...")
        get_or_run_restaurant_analysis(db, sample_restaurant.id)

    print("Seeding complete!")
    db.close()


if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv or "-r" in sys.argv
    seed_data(reset=reset_flag)
