import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Restaurant, Review, Analysis, AnalysisRun, User
from app.routers.auth import ensure_restaurant_access, get_current_user, require_roles
from app.schemas import (
    RestaurantResponse,
    RestaurantDetailResponse,
    RestaurantCreate,
    AnalysisResponse,
    TriggerAnalysisRequest
)
from app.services.analysis import get_or_run_restaurant_analysis
from app.services.tts import (
    TTSModelLoadingError,
    TTSNotConfiguredError,
    TTSQuotaError,
    TTSTimeoutError,
    TTSUpstreamError,
    synthesize_speech,
)

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[RestaurantResponse])
def list_restaurants(
    q: Optional[str] = Query(None, description="Search by restaurant name or address"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(
        Restaurant,
        func.count(Review.id).label("review_count")
    ).outerjoin(Review, Restaurant.id == Review.restaurant_id).group_by(Restaurant.id)

    if current_user.role == "OWNER":
        query = query.join(Restaurant.owners).filter(User.id == current_user.id)

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
def get_restaurant_detail(
    restaurant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restaurant with ID {restaurant_id} not found"
        )
    ensure_restaurant_access(restaurant, current_user)

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
def create_restaurant(
    payload: RestaurantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "OWNER")),
):
    existing = db.query(Restaurant).filter(Restaurant.google_place_id == payload.google_place_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Restaurant with Google Place ID '{payload.google_place_id}' already exists."
        )

    restaurant = Restaurant(**payload.model_dump())
    if current_user.role == "OWNER":
        restaurant.owners.append(current_user)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    ensure_restaurant_access(restaurant, current_user)
    try:
        analysis = get_or_run_restaurant_analysis(
            db=db,
            restaurant_id=restaurant_id,
            force_refresh=request.force_refresh,
            requested_model=request.model
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze restaurant"
        )

    try:
        db.add(AnalysisRun(user_id=current_user.id, analysis_id=analysis.id))
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Failed to record analysis history")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record analysis history"
        ) from e
    return analysis


@router.get("/{restaurant_id}/analyses", response_model=List[AnalysisResponse])
def get_restaurant_analyses_history(
    restaurant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    ensure_restaurant_access(restaurant, current_user)

    analyses = (
        db.query(Analysis)
        .filter(Analysis.restaurant_id == restaurant_id)
        .order_by(Analysis.created_at.desc())
        .all()
    )
    return analyses


@router.post("/{restaurant_id}/analyses/{analysis_id}/tts")
def synthesize_analysis_summary_tts(
    restaurant_id: int,
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    ensure_restaurant_access(restaurant, current_user)

    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.restaurant_id == restaurant_id)
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    summary = (analysis.result_json or {}).get("summary") or ""
    if not isinstance(summary, str) or not summary.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Analysis summary is empty")

    try:
        audio_bytes, media_type = synthesize_speech(summary)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TTSQuotaError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc
    except (TTSNotConfiguredError, TTSModelLoadingError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except TTSTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except TTSUpstreamError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return Response(
        content=audio_bytes,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
