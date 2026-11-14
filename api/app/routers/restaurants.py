from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Restaurant, Review, Analysis
from app.schemas import (
    RestaurantResponse,
    RestaurantDetailResponse,
    RestaurantCreate,
    AnalysisResponse,
    TriggerAnalysisRequest
)
from app.services.analysis import get_or_run_restaurant_analysis

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])


@router.get("", response_model=List[RestaurantResponse])
def list_restaurants(
    q: Optional[str] = Query(None, description="Search by restaurant name or address"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(
        Restaurant,
        func.count(Review.id).label("review_count")
    ).outerjoin(Review, Restaurant.id == Review.restaurant_id).group_by(Restaurant.id)

    if q:
        query = query.filter(
            (Restaurant.name.ilike(f"%{q}%")) | (Restaurant.address.ilike(f"%{q}%"))
        )

    results = query.offset(skip).limit(limit).all()

    response = []
    for restaurant, count in results:
        data = RestaurantResponse.model_validate(restaurant)
        data.review_count = count
        response.append(data)

    return response


@router.get("/{restaurant_id}", response_model=RestaurantDetailResponse)
def get_restaurant_detail(restaurant_id: int, db: Session = Depends(get_db)):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restaurant with ID {restaurant_id} not found"
        )

    latest_analysis = (
        db.query(Analysis)
        .filter(Analysis.restaurant_id == restaurant_id)
        .order_by(Analysis.created_at.desc())
        .first()
    )

    detail = RestaurantDetailResponse.model_validate(restaurant)
    detail.review_count = len(restaurant.reviews)
    detail.reviews = restaurant.reviews
    detail.latest_analysis = latest_analysis
    return detail


@router.post("", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED)
def create_restaurant(payload: RestaurantCreate, db: Session = Depends(get_db)):
    existing = db.query(Restaurant).filter(Restaurant.google_place_id == payload.google_place_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Restaurant with Google Place ID '{payload.google_place_id}' already exists."
        )

    restaurant = Restaurant(**payload.model_dump())
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)

    response = RestaurantResponse.model_validate(restaurant)
    response.review_count = 0
    return response


@router.post("/{restaurant_id}/analyze", response_model=AnalysisResponse)
def run_restaurant_analysis(
    restaurant_id: int,
    request: TriggerAnalysisRequest = TriggerAnalysisRequest(),
    db: Session = Depends(get_db)
):
    try:
        analysis = get_or_run_restaurant_analysis(
            db=db,
            restaurant_id=restaurant_id,
            force_refresh=request.force_refresh,
            requested_model=request.model
        )
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze restaurant: {str(e)}"
        )


@router.get("/{restaurant_id}/analyses", response_model=List[AnalysisResponse])
def get_restaurant_analyses_history(restaurant_id: int, db: Session = Depends(get_db)):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    analyses = (
        db.query(Analysis)
        .filter(Analysis.restaurant_id == restaurant_id)
        .order_by(Analysis.created_at.desc())
        .all()
    )
    return analyses
