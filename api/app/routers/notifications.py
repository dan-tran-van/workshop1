from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification, Restaurant, User
from app.routers.auth import get_current_user
from app.schemas import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationResponse])
def list_notifications(
    restaurant_id: Optional[int] = Query(None, description="Only notifications for this restaurant"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Notification]:
    query = db.query(Notification)
    if current_user.role == "OWNER":
        query = (
            query.join(Restaurant, Notification.restaurant_id == Restaurant.id)
            .join(Restaurant.owners)
            .filter(User.id == current_user.id)
        )
    if restaurant_id is not None:
        query = query.filter(Notification.restaurant_id == restaurant_id)
    return query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(skip).limit(limit).all()
