from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Restaurant, Review
from app.schemas import ReviewResponse, ReviewCreate

router = APIRouter(tags=["Reviews"])


@router.get("/restaurants/{restaurant_id}/reviews", response_model=List[ReviewResponse])
def list_restaurant_reviews(
    restaurant_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

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
    db: Session = Depends(get_db)
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    review_data = payload.model_dump()
    review_data["restaurant_id"] = restaurant_id
    review = Review(**review_data)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
