"""Structured lab-test input API (Phase 1, item 1.6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import Field, SoilRecord, User
from app.schemas import SoilRecordCreate, SoilRecordUpdate, SoilRecordOut

router = APIRouter(prefix="/soil-records", tags=["soil-records"])


@router.post("", response_model=SoilRecordOut, status_code=201)
def create_soil_record(
    payload: SoilRecordCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> SoilRecordOut:
    field = db.get(Field, payload.field_id)
    if field is None:
        raise HTTPException(status_code=404, detail=f"Field {payload.field_id} not found.")

    if field.farm and hasattr(field.farm, "user_id") and field.farm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Field {payload.field_id} not found.")

    data = payload.model_dump(exclude_none=True)
    record = SoilRecord(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{record_id}", response_model=SoilRecordOut)
def get_soil_record(
    record_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> SoilRecordOut:
    record = db.get(SoilRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Soil record not found.")
    
    if record.field and record.field.farm and hasattr(record.field.farm, "user_id") and record.field.farm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Soil record not found.")
    return record


@router.patch("/{record_id}", response_model=SoilRecordOut)
def update_soil_record(
    record_id: int, 
    payload: SoilRecordUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> SoilRecordOut:
    record = db.get(SoilRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Soil record not found.")

    if record.field and record.field.farm and hasattr(record.field.farm, "user_id") and record.field.farm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Soil record not found.")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)
    return record


@router.put("/{record_id}", response_model=SoilRecordOut)
def replace_soil_record(
    record_id: int, 
    payload: SoilRecordUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> SoilRecordOut:
    return update_soil_record(record_id, payload, db, current_user)


@router.get("/by-field/{field_id}", response_model=list[SoilRecordOut])
def list_by_field(
    field_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[SoilRecordOut]:
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(status_code=404, detail=f"Field {field_id} not found.")
    
    if field.farm and hasattr(field.farm, "user_id") and field.farm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Field {field_id} not found.")

    stmt = select(SoilRecord).where(SoilRecord.field_id == field_id).order_by(SoilRecord.sampled_at)
    return list(db.scalars(stmt))