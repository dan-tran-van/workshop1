import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Restaurant, Review, SyncTarget, SyncRun

logger = logging.getLogger(__name__)


def fetch_from_google_places(place_id: str, api_key: str, language: str = "en") -> Optional[Dict[str, Any]]:
    """
    Fetch restaurant details and up to 5 reviews from Google Places API (Place Details).
    """
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "place_id,name,formatted_address,rating,user_ratings_total,reviews",
        "key": api_key,
        "language": language
    }
    try:
        response = httpx.get(url, params=params, timeout=15.0)
        data = response.json()
        if data.get("status") == "OK":
            return data.get("result")
        else:
            logger.warning(f"Google Places API returned status: {data.get('status')} - {data.get('error_message')}")
            return None
    except Exception as e:
        logger.error(f"Error calling Google Places API: {e}")
        return None


def run_sync_for_target(db: Session, target: SyncTarget, sync_run: SyncRun):
    """
    Execute sync for a specific target. Supports Google Places API or mock provider.
    """
    restaurants_count = 0
    reviews_count = 0

    if settings.GOOGLE_PLACES_API_KEY and target.target_type == "place_id":
        place_data = fetch_from_google_places(target.value, settings.GOOGLE_PLACES_API_KEY, target.language_code)
        if place_data:
            restaurant = db.query(Restaurant).filter(Restaurant.google_place_id == place_data.get("place_id")).first()
            now = datetime.now(timezone.utc)
            if not restaurant:
                restaurant = Restaurant(
                    google_place_id=place_data.get("place_id"),
                    name=place_data.get("name", "Unknown Restaurant"),
                    address=place_data.get("formatted_address"),
                    google_rating=place_data.get("rating"),
                    user_rating_count=place_data.get("user_ratings_total"),
                    last_synced_at=now
                )
                db.add(restaurant)
                db.flush()
                restaurants_count += 1
            else:
                restaurant.name = place_data.get("name", restaurant.name)
                restaurant.address = place_data.get("formatted_address", restaurant.address)
                restaurant.google_rating = place_data.get("rating", restaurant.google_rating)
                restaurant.user_rating_count = place_data.get("user_ratings_total", restaurant.user_rating_count)
                restaurant.last_synced_at = now
                restaurants_count += 1

            for rev in place_data.get("reviews", []):
                external_id = f"{restaurant.google_place_id}_{rev.get('time')}"
                existing_rev = db.query(Review).filter(Review.external_review_id == external_id).first()
                if not existing_rev:
                    pub_time = datetime.fromtimestamp(rev.get("time", int(now.timestamp())), tz=timezone.utc)
                    new_rev = Review(
                        restaurant_id=restaurant.id,
                        external_review_id=external_id,
                        author_name=rev.get("author_name", "Anonymous"),
                        author_uri=rev.get("author_url"),
                        rating=float(rev.get("rating", 5.0)),
                        text=rev.get("text", ""),
                        published_at=pub_time
                    )
                    db.add(new_rev)
                    reviews_count += 1
    else:
        # Simulated sync for demonstration & local development
        now = datetime.now(timezone.utc)
        place_id = target.value if target.target_type == "place_id" else f"mock_{target.id}"
        restaurant = db.query(Restaurant).filter(Restaurant.google_place_id == place_id).first()
        if not restaurant:
            restaurant = Restaurant(
                google_place_id=place_id,
                name=f"Sample Restaurant ({target.value})",
                address="123 Culinary Boulevard, Downtown",
                google_rating=4.3,
                user_rating_count=120,
                last_synced_at=now
            )
            db.add(restaurant)
            db.flush()
            restaurants_count += 1
        else:
            restaurant.last_synced_at = now
            restaurants_count += 1

        # Check existing review count
        existing_rev_count = db.query(Review).filter(Review.restaurant_id == restaurant.id).count()
        if existing_rev_count < 3:
            mock_reviews = [
                {
                    "author": "Alice Nguyen",
                    "rating": 5.0,
                    "text": "Incredible dining experience! The truffle pasta was bursting with flavor and the staff made us feel like family. Ambient lighting was great.",
                },
                {
                    "author": "Marcus Lee",
                    "rating": 2.0,
                    "text": "The food tasted great, but we waited 45 minutes for our main course on a Friday evening. Tables were a bit cramped and noisy.",
                },
                {
                    "author": "Sarah Jenkins",
                    "rating": 4.0,
                    "text": "Generous portions and very clean restaurant. Prices are fair for the city center. Will definitely come back for lunch.",
                }
            ]
            for idx, mr in enumerate(mock_reviews):
                ext_id = f"{place_id}_mock_{idx+1}"
                if not db.query(Review).filter(Review.external_review_id == ext_id).first():
                    new_rev = Review(
                        restaurant_id=restaurant.id,
                        external_review_id=ext_id,
                        author_name=mr["author"],
                        rating=mr["rating"],
                        text=mr["text"],
                        published_at=now
                    )
                    db.add(new_rev)
                    reviews_count += 1

    target.last_synced_at = datetime.now(timezone.utc)
    sync_run.restaurants_upserted += restaurants_count
    sync_run.reviews_upserted += reviews_count


def execute_sync_job(db: Session, target_id: Optional[int] = None) -> SyncRun:
    """
    Trigger a sync run across all active targets or a specific target.
    """
    sync_run = SyncRun(status="RUNNING")
    db.add(sync_run)
    db.commit()
    db.refresh(sync_run)

    try:
        query = db.query(SyncTarget).filter(SyncTarget.is_active == True)
        if target_id:
            query = query.filter(SyncTarget.id == target_id)
        
        targets = query.all()
        for target in targets:
            run_sync_for_target(db, target, sync_run)

        sync_run.status = "COMPLETED"
        sync_run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(sync_run)
    except Exception as e:
        logger.exception("Sync job encountered an error")
        sync_run.status = "FAILED"
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.error_message = str(e)
        db.commit()
        db.refresh(sync_run)

    return sync_run
