import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class DiseaseProfile(Base):
    """Disease-pluggable config — Architecture doc §5, Database doc §2.2.

    Application code reads this row per patient; no disease-name branching
    is allowed in application code (Architecture doc §5 hard rule).
    """

    __tablename__ = "disease_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disease_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    rating_scale_code: Mapped[str] = mapped_column(Text, nullable=False)
    rating_scale_min: Mapped[float] = mapped_column(Numeric, nullable=False)
    rating_scale_max: Mapped[float] = mapped_column(Numeric, nullable=False)
    rating_scale_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    corpus_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    ai_behavior_contract: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disease_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disease_profiles.id"), nullable=False)
    preferred_comm_mode: Mapped[str] = mapped_column(Text, nullable=False)
    onboarded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint("preferred_comm_mode IN ('text', 'voice', 'both')"),
    )


class Caregiver(Base):
    __tablename__ = "caregivers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PatientCaregiverLink(Base):
    __tablename__ = "patient_caregiver_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    caregiver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("caregivers.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, default="family", nullable=False)
    status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("patient_id", "caregiver_id"),
        CheckConstraint("role IN ('family', 'clinician')"),
        CheckConstraint("status IN ('active', 'revoked')"),
    )


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    dosage: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_rrule: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ConsentRecord(Base):
    """Append-only — Database doc §2.4. Never UPDATE a row; insert a new one."""

    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    version: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "category IN ('symptom_data', 'fall_location_data', 'research_personalization', "
            "'caregiver_sharing', 'literature_digest')"
        ),
    )


class CorpusSource(Base):
    """Bridge row to the vector DB — Database doc §5. `vector_id` is the ID in
    whichever vector store Architecture doc §8 resolves to (pgvector row or
    Pinecone vector ID); not modeled here since that decision is still open.
    """

    __tablename__ = "corpus_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disease_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disease_profiles.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    clinician_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vector_id: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint("source_type IN ('pubmed_abstract', 'clinical_guideline', 'patient_forum_consented')"),
    )
