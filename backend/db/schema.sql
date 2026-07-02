-- AI Caregiver — initial schema
-- Mirrors 04-Database/DATABASE_DESIGN.md. Run automatically by docker-compose
-- (timescale/timescaledb image executes docker-entrypoint-initdb.d/*.sql on
-- first boot only — re-run manually against an existing volume if changed).

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()

-- ── 2.2 Disease-pluggable config (create before patients: FK target) ───────

CREATE TABLE disease_profiles (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disease_code         TEXT NOT NULL UNIQUE,
    display_name         TEXT NOT NULL,
    rating_scale_code    TEXT NOT NULL,
    rating_scale_min     NUMERIC NOT NULL,
    rating_scale_max     NUMERIC NOT NULL,
    rating_scale_config  JSONB NOT NULL,
    corpus_namespace     TEXT NOT NULL,
    ai_behavior_contract TEXT NOT NULL,
    active               BOOLEAN NOT NULL DEFAULT true,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 2.1 Identity & relationships ────────────────────────────────────────────

CREATE TABLE patients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disease_profile_id  UUID NOT NULL REFERENCES disease_profiles(id),
    preferred_comm_mode TEXT NOT NULL CHECK (preferred_comm_mode IN ('text', 'voice', 'both')),
    onboarded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE caregivers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deleted_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE patient_caregiver_links (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id   UUID NOT NULL REFERENCES patients(id),
    caregiver_id UUID NOT NULL REFERENCES caregivers(id),
    role         TEXT NOT NULL DEFAULT 'family' CHECK (role IN ('family', 'clinician')),
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    granted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at   TIMESTAMPTZ,
    UNIQUE (patient_id, caregiver_id)
);

-- ── 2.3 Medications ──────────────────────────────────────────────────────────

CREATE TABLE medications (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id     UUID NOT NULL REFERENCES patients(id),
    name           TEXT NOT NULL,
    dosage         TEXT NOT NULL,
    schedule_rrule TEXT NOT NULL,
    active         BOOLEAN NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 2.4 Consent ──────────────────────────────────────────────────────────────

CREATE TABLE consent_records (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id),
    category   TEXT NOT NULL CHECK (category IN (
                   'symptom_data', 'fall_location_data', 'research_personalization',
                   'caregiver_sharing', 'literature_digest'
               )),
    granted    BOOLEAN NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    version    TEXT NOT NULL
);

-- ── 5. Vector DB reference table ────────────────────────────────────────────

CREATE TABLE corpus_sources (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disease_profile_id  UUID NOT NULL REFERENCES disease_profiles(id),
    title               TEXT NOT NULL,
    source_type         TEXT NOT NULL CHECK (source_type IN ('pubmed_abstract', 'clinical_guideline', 'patient_forum_consented')),
    clinician_reviewed  BOOLEAN NOT NULL DEFAULT false,
    url                 TEXT,
    vector_id           TEXT NOT NULL,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 3. Time-series (TimescaleDB hypertables) ────────────────────────────────

CREATE TABLE medication_adherence_events (
    id            UUID DEFAULT gen_random_uuid(),
    patient_id    UUID NOT NULL REFERENCES patients(id),
    medication_id UUID NOT NULL REFERENCES medications(id),
    scheduled_for TIMESTAMPTZ NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('confirmed', 'missed', 'snoozed')),
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, recorded_at)
);
SELECT create_hypertable('medication_adherence_events', 'recorded_at');

CREATE TABLE checkins (
    id             UUID DEFAULT gen_random_uuid(),
    patient_id     UUID NOT NULL REFERENCES patients(id),
    checkin_type   TEXT NOT NULL CHECK (checkin_type IN ('structured', 'mood_row')),
    answers        JSONB NOT NULL,
    computed_score NUMERIC,
    input_mode     TEXT NOT NULL CHECK (input_mode IN ('text', 'voice')),
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, recorded_at)
);
SELECT create_hypertable('checkins', 'recorded_at');

CREATE TABLE symptom_events (
    id             UUID DEFAULT gen_random_uuid(),
    patient_id     UUID NOT NULL REFERENCES patients(id),
    event_type     TEXT NOT NULL CHECK (event_type IN ('fall', 'near_fall', 'sensor_alert')),
    source         TEXT NOT NULL CHECK (source IN ('checkin_answer', 'wearable_webhook')),
    sensor_payload JSONB,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, recorded_at)
);
SELECT create_hypertable('symptom_events', 'recorded_at');

CREATE TABLE alerts (
    id              UUID DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id),
    triggered_by    TEXT NOT NULL CHECK (triggered_by IN ('missed_medication', 'symptom_event', 'flagged_checkin_answer')),
    source_table    TEXT NOT NULL,
    source_id       UUID NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('info', 'urgent')),
    acknowledged_by UUID REFERENCES caregivers(id),
    acknowledged_at TIMESTAMPTZ,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, recorded_at)
);
SELECT create_hypertable('alerts', 'recorded_at');

-- ── 7. Audit log ─────────────────────────────────────────────────────────────

CREATE TABLE audit_log (
    id            UUID DEFAULT gen_random_uuid(),
    actor_type    TEXT NOT NULL CHECK (actor_type IN ('patient', 'caregiver', 'system', 'ai_agent')),
    actor_id      UUID,
    action        TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id   UUID,
    metadata      JSONB,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, occurred_at)
);
SELECT create_hypertable('audit_log', 'occurred_at');

-- audit_log is append-only at the DB role level (Database doc §7) — revoke
-- UPDATE/DELETE from the application role once that role exists:
-- REVOKE UPDATE, DELETE ON audit_log FROM app_role;

-- ── Seed: Parkinson's disease profile (MVP, per PRD Scope & Sequencing) ────

INSERT INTO disease_profiles (
    disease_code, display_name, rating_scale_code, rating_scale_min, rating_scale_max,
    rating_scale_config, corpus_namespace, ai_behavior_contract, active
) VALUES (
    'parkinsons',
    E'Parkinson’s Disease',
    'UPDRS',
    0,
    199,
    '{"questions": [
        {"id": "medication_on_time", "prompt": "Did you take your medication on time today?", "options": ["Yes", "No", "Not yet"]},
        {"id": "falls", "prompt": "Any falls or near-falls since your last check-in?", "options": ["No", "Yes"]},
        {"id": "movement_today", "prompt": "How are your movements today?", "scale": [1, 5]}
    ]}'::jsonb,
    'parkinsons_v1',
    'Role: medical assistant agent for patients with Parkinson''s disease.
Responsibilities:
  1. Ask daily UPDRS-based check-in questions.
  2. Remind about medication per patient''s own schedule.
  3. Offer short guided routines (e.g., 5-minute walking) when appropriate.
  4. Answer patient/caregiver questions using tool calls (record lookup, RAG
     retrieval, trial search) -- never answer patient-data or medical-fact
     questions from unaided generation.
Constraints:
  - Never provide a diagnosis.
  - Never suggest medication dose changes.
  - Always cite sources for any factual/research claim (RAG-retrieved, not
    from training data).
  - Escalate to caregiver/clinician when check-in answers indicate a concerning change.
Tone: empathetic, concise, plain language.',
    true
);
