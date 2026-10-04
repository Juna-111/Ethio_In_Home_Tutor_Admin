from datetime import datetime
from typing import Any, List, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, UniqueConstraint, false, func
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
    entrance_result_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entrance_result: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Canonical values: pending, verified, probation, rejected. `verified` is
    # checklist-approved and match-eligible; pause is tracked by is_paused.
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class AdminUser(Base):
    __tablename__ = "admin_users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="admin", index=True)
    added_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TutorVerification(Base):
    __tablename__ = "tutor_verifications"

    tutor_id: Mapped[int] = mapped_column(ForeignKey("tutors.id"), primary_key=True)
    id_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    entrance_result_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    phone_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    claims_plausible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="miniapp", server_default="miniapp")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


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
    __table_args__ = (
        UniqueConstraint("request_id", "tutor_id", name="uq_match_invites_request_tutor"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("parent_requests.id"), nullable=False, index=True)
    tutor_id: Mapped[int] = mapped_column(ForeignKey("tutors.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="sent", index=True)  # sent, yes, no, expired
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("parent_requests.id"), nullable=False, index=True, unique=True)
    tutor_id: Mapped[int] = mapped_column(ForeignKey("tutors.id"), nullable=False, index=True)
    assigned_by: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", index=True)


class SessionFeedback(Base):
    __tablename__ = "session_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(Integer, ForeignKey("assignments.id"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[str] = mapped_column(String(20), nullable=False, default="parent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TutorIncident(Base):
    __tablename__ = "tutor_incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tutor_id: Mapped[int] = mapped_column(Integer, ForeignKey("tutors.id"), nullable=False, index=True)
    request_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parent_requests.id"), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="low")  # low|medium|high
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    reported_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ScheduledEventClaim(Base):
    __tablename__ = "scheduled_event_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    check_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    topic_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class RegistrationFunnelEvent(Base):
    __tablename__ = "registration_funnel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    tutor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tutors.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

