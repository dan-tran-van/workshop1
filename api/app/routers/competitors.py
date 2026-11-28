from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Restaurant, User
from app.routers.auth import ensure_restaurant_access, require_roles
from app.schemas import (
    CompetitiveSetResponse,
    CompetitorCandidate,
    CompetitorSelectionRequest,
    GapExplanationResponse,
    GapTableResponse,
)
from app.services.competitors import (
    InsufficientDataError,
    build_competitive_set,
    build_gap_table,
    clear_selection,
    explain_gap,
    list_manual_candidates,
    set_selection,
)

router = APIRouter(prefix="/restaurants/{restaurant_id}/competitors", tags=["Market Comparison"])

# Owners use market comparison for their own restaurants; analysts can view any restaurant.
# Only owners change the competitive set. Admins do not use this feature.
view_roles = require_roles("OWNER", "ANALYST")
edit_roles = require_roles("OWNER")


def _restaurant_for(db: Session, restaurant_id: int, user: User) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    ensure_restaurant_access(restaurant, user)
    return restaurant


@router.get("", response_model=CompetitiveSetResponse)
def get_competitive_set(
    restaurant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(view_roles),
) -> dict:
    restaurant = _restaurant_for(db, restaurant_id, user)
    return build_competitive_set(db, restaurant, can_edit=user.role == "OWNER")


@router.get("/candidates", response_model=List[CompetitorCandidate])
def get_manual_candidates(
    restaurant_id: int,
    q: Optional[str] = Query(None, description="Search by restaurant name or address"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(edit_roles),
) -> List[dict]:
    restaurant = _restaurant_for(db, restaurant_id, user)
    return list_manual_candidates(db, restaurant, q.strip() if q else None, limit)


@router.put("/{competitor_id}", response_model=CompetitiveSetResponse)
def update_competitor_selection(
    restaurant_id: int,
    competitor_id: int,
    payload: CompetitorSelectionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(edit_roles),
) -> dict:
    restaurant = _restaurant_for(db, restaurant_id, user)
    competitor = db.query(Restaurant).filter(Restaurant.id == competitor_id).first()
    if competitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor restaurant not found")
    try:
        set_selection(db, restaurant, competitor, payload.status, user.id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return build_competitive_set(db, restaurant, can_edit=True)


@router.delete("/{competitor_id}", response_model=CompetitiveSetResponse)
def reset_competitor_selection(
    restaurant_id: int,
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(edit_roles),
) -> dict:
    restaurant = _restaurant_for(db, restaurant_id, user)
    clear_selection(db, restaurant, competitor_id)
    return build_competitive_set(db, restaurant, can_edit=True)


@router.get("/gap", response_model=GapTableResponse)
def get_gap_table(
    restaurant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(view_roles),
) -> dict:
    restaurant = _restaurant_for(db, restaurant_id, user)
    return build_gap_table(db, restaurant)


@router.post("/gap/{aspect}/explain", response_model=GapExplanationResponse)
def explain_gap_for_criterion(
    restaurant_id: int,
    aspect: str,
    db: Session = Depends(get_db),
    user: User = Depends(view_roles),
) -> dict:
    restaurant = _restaurant_for(db, restaurant_id, user)
    try:
        return explain_gap(db, restaurant, aspect)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown criterion '{aspect}'") from error
    except InsufficientDataError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
