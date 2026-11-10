"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field as PydField, model_validator


class RegisterRequest(BaseModel):
    phone: str | None = None
    email: str | None = None
    name: str | None = None
    password: str
    preferred_language: str = PydField(default="en", pattern="^(en|hi|kn|te)$")

    @model_validator(mode="before")
    @classmethod
    def _map_frontend_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Gracefully remap frontend labels to backend schema expectations
            if "mobile" in data and not data.get("phone"):
                data["phone"] = data.get("mobile")
            if "username" in data and not data.get("name"):
                data["name"] = data.get("username")
        return data

    @model_validator(mode="after")
    def _require_an_identifier(self) -> "RegisterRequest":
        if not (self.phone or "").strip() and not (self.email or "").strip():
            raise ValueError("Provide a mobile number or an email address to create an account.")
        if not (self.name or "").strip():
            self.name = "New Farmer"
        return self


class LoginRequest(BaseModel):
    identifier: str | None = None
    phone: str | None = None
    email: str | None = None
    password: str

    @model_validator(mode="before")
    @classmethod
    def _map_frontend_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "mobile" in data and not data.get("identifier") and not data.get("phone"):
                data["identifier"] = data.get("mobile")
            if "username" in data and not data.get("identifier"):
                data["identifier"] = data.get("username")
        return data

    @model_validator(mode="after")
    def _require_an_identifier(self) -> "LoginRequest":
        if not (self.identifier or self.phone or self.email):
            raise ValueError("Provide your mobile number or email address.")
        return self

    @property
    def resolved_identifier(self) -> str:
        return (self.identifier or self.phone or self.email or "").strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    phone: str | None
    email: str | None
    name: str
    preferred_language: str
    created_at: datetime


class FarmCreate(BaseModel):
    name: str
    owner_name: str | None = None
    location: str | None = None


class FarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    owner_name: str | None
    location: str | None
    created_at: datetime


class FieldCreate(BaseModel):
    farm_id: int
    name: str
    area_hectares: float | None = None
    latitude: float | None = None
    longitude: float | None = None


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    farm_id: int
    name: str
    area_hectares: float | None
    latitude: float | None
    longitude: float | None
    created_at: datetime


class SoilRecordCreate(BaseModel):
    field_id: int
    nitrogen: float | None = PydField(default=None, ge=0)
    phosphorus: float | None = PydField(default=None, ge=0)
    potassium: float | None = PydField(default=None, ge=0)
    ph: float | None = PydField(default=None, ge=0, le=14)
    organic_matter: float | None = PydField(default=None, ge=0, le=100)
    moisture: float | None = PydField(default=None, ge=0, le=100)
    temperature: float | None = None
    humidity: float | None = PydField(default=None, ge=0, le=100)
    rainfall: float | None = PydField(default=None, ge=0)
    sampled_at: datetime | None = None

    _MEASUREMENTS = ("nitrogen", "phosphorus", "potassium", "ph", "organic_matter", "moisture")

    @model_validator(mode="after")
    def _validate_data(self) -> "SoilRecordCreate":
        if all(getattr(self, name) is None for name in self._MEASUREMENTS):
            raise ValueError("Provide at least one soil measurement.")
        
        for nutrient, max_val in [("nitrogen", 140.0), ("phosphorus", 80.0), ("potassium", 205.0)]:
            val = getattr(self, nutrient)
            if val is not None and val > max_val:
                raise ValueError(f"INDEX error: {nutrient} value {val} exceeds trained scale bound ({max_val}).")

        if self.ph is not None and not (3.0 <= self.ph <= 10.0):
            raise ValueError(f"pH {self.ph} is outside the typical soil range (3–10).")
        return self


class SoilRecordUpdate(BaseModel):
    nitrogen: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    ph: float | None = None
    organic_matter: float | None = None
    moisture: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    rainfall: float | None = None
    sampled_at: datetime | None = None
    
    @model_validator(mode="after")
    def _validate_scales(self) -> "SoilRecordUpdate":
        for nutrient, max_val in [("nitrogen", 140.0), ("phosphorus", 80.0), ("potassium", 205.0)]:
            val = getattr(self, nutrient)
            if val is not None and val > max_val:
                raise ValueError(f"INDEX error: {nutrient} value {val} exceeds trained scale bound ({max_val}).")
        return self


class SoilRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    field_id: int
    nitrogen: float | None
    phosphorus: float | None
    potassium: float | None
    ph: float | None
    organic_matter: float | None
    moisture: float | None
    temperature: float | None
    humidity: float | None
    rainfall: float | None
    sampled_at: datetime
    created_at: datetime


class AnalyzeRequest(BaseModel):
    field_id: int
    soil_record_id: int | None = None
    nitrogen: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    ph: float | None = None
    ec: float | None = None
    s: float | None = None
    cu: float | None = None
    fe: float | None = None
    mn: float | None = None
    zn: float | None = None
    b: float | None = None
    organic_matter: float | None = None
    moisture: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    rainfall: float | None = None  
    image_id: int | None = None
    explain: bool = False
    fuse: bool = False
    include_history: bool = True
    persist: bool = True

    @model_validator(mode="after")
    def _validate_inline_scales(self) -> "AnalyzeRequest":
        for nutrient, max_val in [("nitrogen", 140.0), ("phosphorus", 80.0), ("potassium", 205.0)]:
            val = getattr(self, nutrient)
            if val is not None and val > max_val:
                raise ValueError(f"INDEX error: {nutrient} value {val} exceeds trained scale bound ({max_val}).")
        return self


class AnalysisResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    field_id: int
    soil_record_id: int | None
    image_id: int | None
    soil_health_score: float | None
    diagnosis: str | None
    degradation_risk_index: float | None
    recommended_crop: str | None
    created_at: datetime


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    field_id: int | None
    original_filename: str | None
    stored_path: str
    processed_path: str | None
    content_type: str | None
    source: str
    file_size: int | None
    width: int | None
    height: int | None
    created_at: datetime


NUTRIENT_INDEX_MAX = {
    "nitrogen": 140.0,
    "phosphorus": 80.0,
    "potassium": 205.0,
}


def _check_nutrient_scale(obj: object) -> None:
    for name, limit in NUTRIENT_INDEX_MAX.items():
        val = getattr(obj, name, None)
        if val is not None and val > limit:
            raise ValueError(f"INDEX error: {name} value {val} exceeds trained scale bound ({limit}).")


