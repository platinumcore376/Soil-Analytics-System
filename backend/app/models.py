"""Database schema (Phase 1, item 1.3).

Hierarchy:  User 1---* Farm 1---* Field 1---* {SoilRecord, Image, AnalysisResult}
AnalysisResult rows over time enable long-term degradation trend tracking.

Ownership is enforced at the Farm level: every read walks back to `farms.user_id` so a
farmer only ever sees their own data. Fields, records, images and analyses inherit
ownership through their farm rather than carrying a duplicate user_id, which would let the
two disagree.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """A farmer or extension-officer account.

    Sign-in accepts EITHER a phone number or an email address. Phone is the primary
    identity for smallholder farmers, where a mobile number is near-universal; email
    suits extension officers and anyone reaching the app from a desktop.

    Both columns are nullable but at least one must be present -- enforced in the schema
    layer (RegisterRequest) rather than by a DB constraint, so the error message can name
    the actual problem instead of surfacing an IntegrityError.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # bcrypt hash. Never the password itself, and never logged.
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farms: Mapped[list["Farm"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable so the column can be added to a table that already holds rows. Every farm
    # created through the API gets an owner; a NULL means a pre-auth legacy row, and those
    # are invisible to all users rather than visible to everyone.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User | None"] = relationship(back_populates="farms")
    fields: Mapped[list["Field"]] = relationship(
        back_populates="farm", cascade="all, delete-orphan"
    )


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    area_hectares: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped["Farm"] = relationship(back_populates="fields")
    soil_records: Mapped[list["SoilRecord"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )
    images: Mapped[list["Image"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )


class SoilRecord(Base):
    """Structured lab test values for a field at a point in time (item 1.6)."""

    __tablename__ = "soil_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), index=True
    )

    nitrogen: Mapped[float | None] = mapped_column(Float)          # N
    phosphorus: Mapped[float | None] = mapped_column(Float)        # P
    potassium: Mapped[float | None] = mapped_column(Float)         # K
    ph: Mapped[float | None] = mapped_column(Float)
    organic_matter: Mapped[float | None] = mapped_column(Float)    # %
    moisture: Mapped[float | None] = mapped_column(Float)          # %

    # Optional environmental context (aligns with structured ML dataset)
    temperature: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    rainfall: Mapped[float | None] = mapped_column(Float)

    sampled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    field: Mapped["Field"] = relationship(back_populates="soil_records")


class Image(Base):
    """Uploaded soil image + preprocessing metadata (items 1.4, 1.5, 1.7)."""

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int | None] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), index=True
    )

    original_filename: Mapped[str | None] = mapped_column(String(300))
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    processed_path: Mapped[str | None] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(50), default="upload")  # upload | camera
    file_size: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    field: Mapped["Field"] = relationship(back_populates="images")


class AnalysisResult(Base):
    """Model/rule outputs per field over time — powers degradation trend tracking."""

    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), index=True
    )
    soil_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("soil_records.id", ondelete="SET NULL")
    )
    image_id: Mapped[int | None] = mapped_column(
        ForeignKey("images.id", ondelete="SET NULL")
    )

    soil_health_score: Mapped[float | None] = mapped_column(Float)
    diagnosis: Mapped[str | None] = mapped_column(Text)             # JSON string
    degradation_risk_index: Mapped[float | None] = mapped_column(Float)
    recommended_crop: Mapped[str | None] = mapped_column(String(100))
    result_json: Mapped[str | None] = mapped_column(Text)           # full /analyze response, JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    field: Mapped["Field"] = relationship(back_populates="analysis_results")