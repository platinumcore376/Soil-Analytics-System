"""Farm & Field CRUD (supporting item 1.3 / per-field record keeping)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user  # Assuming multi-tenant ownership check uses current user dependency
from app.models import Farm, Field, User
from app.schemas import FarmCreate, FarmOut, FieldCreate, FieldOut

router = APIRouter(tags=["farms"])


@router.post("/farms", response_model=FarmOut, status_code=201)
def create_farm(
    payload: FarmCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> FarmOut:
    farm_data = payload.model_dump()
    # Associate farm with current user if user_id column exists
    if hasattr(Farm, "user_id"):
        farm_data["user_id"] = current_user.id
    farm = Farm(**farm_data)
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


@router.get("/farms", response_model=list[FarmOut])
def list_farms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[FarmOut]:
    stmt = select(Farm)
    if hasattr(Farm, "user_id"):
        stmt = stmt.where(Farm.user_id == current_user.id)
    stmt = stmt.order_by(Farm.id)
    return list(db.scalars(stmt))


@router.post("/fields", response_model=FieldOut, status_code=201)
def create_field(
    payload: FieldCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> FieldOut:
    farm = db.get(Farm, payload.farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail=f"Farm {payload.farm_id} not found.")
    
    # Enforce ownership check if farm has user_id
    if hasattr(Farm, "user_id") and getattr(farm, "user_id", None) != current_user.id:
        raise HTTPException(status_code=404, detail=f"Farm {payload.farm_id} not found.")

    field = Field(**payload.model_dump())
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


@router.get("/farms/{farm_id}/fields", response_model=list[FieldOut])
def list_fields(
    farm_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[FieldOut]:
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail=f"Farm {farm_id} not found.")
        
    # Enforce ownership check if farm has user_id
    if hasattr(Farm, "user_id") and getattr(farm, "user_id", None) != current_user.id:
        raise HTTPException(status_code=404, detail=f"Farm {farm_id} not found.")

    stmt = select(Field).where(Field.farm_id == farm_id).order_by(Field.id)
    return list(db.scalars(stmt))