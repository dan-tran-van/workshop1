from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SyncTarget, SyncRun
from app.schemas import SyncTargetCreate, SyncTargetResponse, SyncRunResponse
from app.services.sync import execute_sync_job

router = APIRouter(prefix="/sync", tags=["Sync Jobs"])


@router.get("/targets", response_model=List[SyncTargetResponse])
def list_sync_targets(db: Session = Depends(get_db)):
    return db.query(SyncTarget).order_by(SyncTarget.id.asc()).all()


@router.post("/targets", response_model=SyncTargetResponse, status_code=status.HTTP_201_CREATED)
def create_sync_target(payload: SyncTargetCreate, db: Session = Depends(get_db)):
    target = SyncTarget(**payload.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


@router.post("/run", response_model=SyncRunResponse)
def trigger_sync(
    target_id: Optional[int] = Query(None, description="Optional target ID to sync single target"),
    db: Session = Depends(get_db)
):
    if target_id:
        target = db.query(SyncTarget).filter(SyncTarget.id == target_id).first()
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sync target {target_id} not found")

    run = execute_sync_job(db=db, target_id=target_id)
    return run


@router.get("/runs", response_model=List[SyncRunResponse])
def list_sync_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    return db.query(SyncRun).order_by(SyncRun.started_at.desc()).offset(skip).limit(limit).all()
