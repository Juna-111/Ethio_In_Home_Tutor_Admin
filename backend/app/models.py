from datetime import datetime
from typing import Any, List, Optional
from sqlalchemy import BigInteger, DateTime, Float, Integer, Numeric, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ParentRequest(Base):
    __tablename__ = "parent_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    parent_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    student_level: Mapped[str] = mapped_column(String(100), nullable=False)
    subjects: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    preferred_gender: Mapped[str] = mapped_column(String(50), nullable=False, default="No preference", index=True)
    preferred_experience: Mapped[str] = mapped_column(String(100), nullable=False, default="Any")
    location_subcity: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    location_landmark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    schedule_days: Mapped[Any] = mapped_column(JSON, nullable=False)
    time_slot: Mapped[str] = mapped_column(String(100), nullable=False)
    session_duration: Mapped[str] = mapped_column(String(50), nullable=False)
    budget_etb: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    telegram_topic_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )


class Tutor(Base):
    __tablename__ = "tutors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    gender: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    university: Mapped[str] = mapped_column(String(150), nullable=False)
    department: Mapped[str] = mapped_column(String(150), nullable=False)
    education_year: Mapped[str] = mapped_column(String(100), nullable=False)
    subjects_qualified: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    grades_qualified: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    years_of_experience: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expected_fee_etb: Mapped[float] = mapped_column(Float, nullable=False)
    base_subcity: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    coverage_areas: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    availability_schedule: Mapped[Any] = mapped_column(JSON, nullable=False)
    id_document_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class AdminWizardState(Base):
    __tablename__ = "admin_wizard_states"

    admin_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )


class MatchInvite(Base):
    __tablename__ = "match_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tutor_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="sent", index=True)  # sent, yes, no, expired
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

