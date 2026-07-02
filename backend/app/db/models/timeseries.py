"""TimescaleDB hypertables — Database doc §3.

Composite primary key (id, recorded_at) matches the hypertable partitioning
requirement (Timescale requires the partitioning column in every unique/PK
constraint).
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class MedicationAdherenceEvent(Base):
    __tablename__ = "medication_adherence_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    medication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medications.id"), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(primary_key=True, server_default=func.now())

    __table_args__ = (CheckConstraint("status IN ('confirmed', 'missed', 'snoozed')"),)


class Checkin(Base):
    """`checkin_type` distinguishes the full structured UPDRS/CDR/EDSS flow from
    the lightweight daily mood-row ping (Product/UX doc §3.1a) — these are
    deliberately modeled as one table with a type discriminator, not two
    tables, since both feed the same `get_checkin_history` tool (Architecture
    doc §4) and Trends view (Product/UX doc §6).
    """

    __tablename__ = "checkins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    checkin_type: Mapped[str] = mapped_column(Text, nullable=False)
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_score: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    input_mode: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(primary_key=True, server_default=func.now())

    __table_args__ = (
        CheckConstraint("checkin_type IN ('structured', 'mood_row')"),
        CheckConstraint("input_mode IN ('text', 'voice')"),
    )


class SymptomEvent(Base):
    __tablename__ = "symptom_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    sensor_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(primary_key=True, server_default=func.now())

    __table_args__ = (
        CheckConstraint("event_type IN ('fall', 'near_fall', 'sensor_alert')"),
        CheckConstraint("source IN ('checkin_answer', 'wearable_webhook')"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    source_table: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("caregivers.id"), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(primary_key=True, server_default=func.now())

    __table_args__ = (
        CheckConstraint("triggered_by IN ('missed_medication', 'symptom_event', 'flagged_checkin_answer')"),
        CheckConstraint("severity IN ('info', 'urgent')"),
    )


class AuditLog(Base):
    """Append-only (Database doc §7) — UPDATE/DELETE grants revoked at the DB
    role level for the application role, not just by application-code
    discipline. See db/schema.sql for the REVOKE statement.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    event_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(primary_key=True, server_default=func.now())

    __table_args__ = (
        CheckConstraint("actor_type IN ('patient', 'caregiver', 'system', 'ai_agent')"),
    )
