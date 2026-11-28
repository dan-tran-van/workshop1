from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Restaurant, Review, User
from app.schemas import ReviewResponse, ReviewCreate, ReviewSearchResponse
from app.routers.auth import ensure_restaurant_access, get_current_user, require_roles
from app.services.vector_store import search_reviews

router = APIRouter(tags=["Reviews"])


@router.get("/reviews/search", response_model=ReviewSearchResponse)
def search_restaurant_reviews(
    q: str = Query(..., min_length=1, description="Search query (semantic or keyword)"),
    restaurant_id: Optional[int] = Query(None, ge=1, description="Optional restaurant ID to scope search"),
    limit: int = Query(10, ge=1, le=100),
    min_similarity: Optional[float] = Query(None, ge=-1.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not q.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Query 'q' must not be blank")

    if restaurant_id is not None:
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not restaurant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        ensure_restaurant_access(restaurant, current_user)
        scoped_ids: Optional[List[int]] = [restaurant.id]
    elif current_user.role == "OWNER":
        scoped_ids = [owned.id for owned in current_user.restaurants]
    else:
        scoped_ids = None

    return search_reviews(
        db,
        query=q,
        restaurant_ids=scoped_ids,
        limit=limit,
        min_similarity=min_similarity,
    )


@router.get("/restaurants/{restaurant_id}/reviews", response_model=List[ReviewResponse])
def list_restaurant_reviews(
    restaurant_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    ensure_restaurant_access(restaurant, current_user)

    reviews = (
        db.query(Review)
        .filter(Review.restaurant_id == restaurant_id)
        .order_by(Review.published_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return reviews


@router.post("/restaurants/{restaurant_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review_for_restaurant(
    restaurant_id: int,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("ADMIN")),
):
    if payload.restaurant_id is not None and payload.restaurant_id != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Body restaurant_id does not match URL path parameter."
        )

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    if payload.external_review_id:
        existing = db.query(Review).filter(Review.external_review_id == payload.external_review_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Review with external ID '{payload.external_review_id}' already exists."
            )

    review_data = payload.model_dump()
    review_data["restaurant_id"] = restaurant_id
    review = Review(**review_data)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
