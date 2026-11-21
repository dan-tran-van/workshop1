import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Notification, Review

logger = logging.getLogger(__name__)

IN_APP_CHANNEL = "in_app"


def is_bad_review(review: Review) -> bool:
    return review.rating <= settings.BAD_REVIEW_RATING_THRESHOLD


def notify_bad_reviews(db: Session, reviews: List[Review], sync_run_id: Optional[int] = None) -> List[Notification]:
    """
    Record an in-app notification for each newly synced review at or below the rating threshold.
    Failures are logged and never propagate, so a completed sync is never turned into an error.
    """
    if not settings.BAD_REVIEW_NOTIFICATIONS_ENABLED:
        return []

    bad_reviews = [review for review in reviews if is_bad_review(review)]
    if not bad_reviews:
        return []

    try:
        now = datetime.now(timezone.utc)
        notifications: List[Notification] = []
        for review in bad_reviews:
            already_notified = (
                db.query(Notification)
                .filter(Notification.review_id == review.id, Notification.channel == IN_APP_CHANNEL)
                .first()
            )
            if already_notified:
                continue
            notification = Notification(
                restaurant_id=review.restaurant_id,
                review_id=review.id,
                sync_run_id=sync_run_id,
                channel=IN_APP_CHANNEL,
                status="SENT",
                sent_at=now
            )
            db.add(notification)
            notifications.append(notification)
        db.commit()
    except Exception:
        logger.exception("Failed to record bad review notifications")
        db.rollback()
        return []

    for notification in notifications:
        logger.warning(
            "Bad review alert: restaurant_id=%s review_id=%s rating=%s",
            notification.restaurant_id, notification.review_id, notification.review.rating
        )
    return notifications
