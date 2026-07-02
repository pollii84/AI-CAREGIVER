# Database Design — AI Caregiver for Neurodegenerative Patients

**Status:** Draft v0.1
**Depends on:** [01-PRD/PRD.md](../01-PRD/PRD.md), [02-Software-Architecture/ARCHITECTURE.md](../02-Software-Architecture/ARCHITECTURE.md), [03-Product-UX-Design-Frontend/PRODUCT_UX_DESIGN.md](../03-Product-UX-Design-Frontend/PRODUCT_UX_DESIGN.md)
**Last updated:** 2026-07-02

---

## 1. Store Split (per Architecture doc §3)

| Store | Contains | Why not the others |
| --- | --- | --- |
| **PostgreSQL** | Patients, caregivers, links, consent, medications, disease profiles, audit log | Compliance-critical relational integrity — this is the data that must never have an orphaned or ambiguous relationship |
| **TimescaleDB** (Postgres extension, same cluster) | Check-ins, mood-row entries, adherence events, symptom/fall events | All time-range-queried — this is the entire Trends/Dashboard surface (Product/UX doc §6) |
| **MongoDB** | Care Agent conversation transcripts, free-text notes | Unstructured, schema-loose by nature; conversation history doesn't benefit from relational constraints |
| **Vector DB** (pgvector, per Architecture doc §8 open decision) | Curated corpus embeddings for `search_corpus` tool | Referenced by ID from Postgres `corpus_source`, not duplicated here |

**Every PHI-bearing table in Postgres/Timescale is encrypted at rest (AES-256) per PRD §8** — this is an infra-layer property (RDS/Timescale Cloud encryption), not per-column, except where noted (§5).

---

## 2. Core Relational Schema (PostgreSQL)

### 2.1 Identity & Relationships

```sql
CREATE TABLE patients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disease_profile_id  UUID NOT NULL REFERENCES disease_profiles(id),
    preferred_comm_mode TEXT NOT NULL CHECK (preferred_comm_mode IN ('text', 'voice', 'both')),
    onboarded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,              -- soft delete, see §6
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Name, DOB, contact info live in the auth/identity provider (OAuth2 layer,
-- Architecture doc §3), not duplicated here — this table holds only what the
-- app logic needs to key off of. Reduces PHI surface in the app DB itself.

CREATE TABLE caregivers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deleted_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE patient_caregiver_links (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id  UUID NOT NULL REFERENCES patients(id),
    caregiver_id UUID NOT NULL REFERENCES caregivers(id),
    role        TEXT NOT NULL DEFAULT 'family' CHECK (role IN ('family', 'clinician')), -- clinician role is phase 2 per PRD scope
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ,
    UNIQUE (patient_id, caregiver_id)
);
-- Multi-caregiver-per-patient is PRD Future/Fast-Follow, not MVP — this table
-- already supports it (no cardinality constraint beyond the UNIQUE pair), so
-- MVP just doesn't build UI for more than one active link.
```

### 2.2 Disease-Pluggable Config (Architecture doc §5)

```sql
CREATE TABLE disease_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disease_code        TEXT NOT NULL UNIQUE,        -- 'parkinsons' | 'alzheimers' | 'ms'
    display_name        TEXT NOT NULL,
    rating_scale_code    TEXT NOT NULL,               -- 'UPDRS' | 'CDR' | 'EDSS'
    rating_scale_min     NUMERIC NOT NULL,
    rating_scale_max     NUMERIC NOT NULL,
    rating_scale_config  JSONB NOT NULL,               -- question set, per-question weight/scoring rules
    corpus_namespace     TEXT NOT NULL,                -- vector DB namespace for search_corpus scoping
    ai_behavior_contract TEXT NOT NULL,                -- disease-specific system prompt variant (PRD §AI Behavior Contract)
    active               BOOLEAN NOT NULL DEFAULT true, -- MVP: only 'parkinsons' active; AD/MS rows exist but inactive until Phase 2/3
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Application code reads `patients.disease_profile_id → disease_profiles` to load scale, corpus scope, and agent system prompt — **no disease-name branching in application code** (Architecture doc §5 hard rule). Adding AD/MS is a data migration (insert/activate a row), not a schema change.

### 2.3 Medications

```sql
CREATE TABLE medications (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id    UUID NOT NULL REFERENCES patients(id),
    name          TEXT NOT NULL,
    dosage        TEXT NOT NULL,
    schedule_rrule TEXT NOT NULL,      -- iCal RRULE format — handles "8am and 4pm daily" cleanly
    active        BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Reminder firing (Notification Service, Architecture doc §3) reads `schedule_rrule` and writes to the `medication_adherence_events` hypertable (§3.1) on confirm/miss — the medication list itself isn't time-series, only the adherence events are.

### 2.4 Consent (PRD §8 — granular, explicit)

```sql
CREATE TABLE consent_records (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id    UUID NOT NULL REFERENCES patients(id),
    category      TEXT NOT NULL CHECK (category IN (
                      'symptom_data', 'fall_location_data', 'research_personalization',
                      'caregiver_sharing', 'literature_digest'
                  )),
    granted       BOOLEAN NOT NULL,
    granted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at    TIMESTAMPTZ,
    version       TEXT NOT NULL          -- consent copy version shown to user, for audit
);
```

One row per category per grant/revoke event (append-only, never updated in place) — the current state is "most recent row per category," but history is preserved. This is what an audit or deletion-request review reads.

---

## 3. Time-Series Schema (TimescaleDB)

All hypertables partition on `recorded_at`. Retention/compression policy: raw data kept indefinitely per PRD (no stated retention limit on clinical history — that's the product's value), but compress chunks older than 90 days (Timescale native compression) to control storage cost without touching query semantics.

### 3.1 Medication Adherence Events

```sql
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
```

Backs: PRD Success Metric "medication adherence rate," Caregiver Dashboard adherence % (Product/UX doc §3.2).

### 3.2 Check-ins (structured, disease-scale-based)

```sql
CREATE TABLE checkins (
    id                UUID DEFAULT gen_random_uuid(),
    patient_id        UUID NOT NULL REFERENCES patients(id),
    checkin_type      TEXT NOT NULL CHECK (checkin_type IN ('structured', 'mood_row')),
    -- 'structured' = full UPDRS/CDR/EDSS flow (Product/UX doc §5)
    -- 'mood_row'   = lightweight daily emoji ping (Product/UX doc §3.1a) — distinct entry
    --                type per that doc's explicit design decision, not a lesser version
    --                of the same thing
    answers           JSONB NOT NULL,     -- question_id → answer, shape defined by disease_profiles.rating_scale_config
    computed_score     NUMERIC,            -- null for mood_row entries
    input_mode        TEXT NOT NULL CHECK (input_mode IN ('text', 'voice')),
    recorded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, recorded_at)
);
SELECT create_hypertable('checkins', 'recorded_at');
```

Backs: `get_checkin_history` Care Agent tool (Architecture doc §4), Trends screen (Product/UX doc §6 — chart reads `computed_score` over time, raw values only, never color-judged per that doc's explicit rule).

### 3.3 Symptom / Emergency Events

```sql
CREATE TABLE symptom_events (
    id            UUID DEFAULT gen_random_uuid(),
    patient_id    UUID NOT NULL REFERENCES patients(id),
    event_type    TEXT NOT NULL CHECK (event_type IN ('fall', 'near_fall', 'sensor_alert')),
    source        TEXT NOT NULL CHECK (source IN ('checkin_answer', 'wearable_webhook')),
    sensor_payload JSONB,        -- full payload for phase-1.5 wearable events, null for checkin-reported
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, recorded_at)
);
SELECT create_hypertable('symptom_events', 'recorded_at');
```

Every insert here **synchronously triggers an alert** (Architecture doc §6 fall-detection data flow — deterministic, no LLM in this path). Consent-gated: an insert from `source = 'wearable_webhook'` requires an active `fall_location_data` consent record (§2.4) or the webhook payload is rejected upstream, never silently dropped without a caregiver-visible reason.

### 3.4 Caregiver Alerts

```sql
CREATE TABLE alerts (
    id              UUID DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id),
    triggered_by    TEXT NOT NULL CHECK (triggered_by IN ('missed_medication', 'symptom_event', 'flagged_checkin_answer')),
    source_table    TEXT NOT NULL,      -- 'medication_adherence_events' | 'symptom_events' | 'checkins'
    source_id       UUID NOT NULL,      -- FK by convention, not enforced (source_table varies)
    severity        TEXT NOT NULL CHECK (severity IN ('info', 'urgent')),
    acknowledged_by UUID REFERENCES caregivers(id),
    acknowledged_at TIMESTAMPTZ,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, recorded_at)
);
SELECT create_hypertable('alerts', 'recorded_at');
```

Backs PRD Success Metric "caregiver alert acknowledgment median time" directly (`acknowledged_at - recorded_at`).

---

## 4. Unstructured Store (MongoDB)

### 4.1 `agent_conversations`

```js
{
  _id: ObjectId,
  patient_id: UUID,              // references Postgres patients.id, not enforced at DB level
  started_at: ISODate,
  messages: [
    {
      role: "user" | "agent",
      content: String,
      tool_calls: [               // present only on agent turns that called a tool
        { tool: "search_corpus", input: {...}, result_ref: String }
      ],
      citations: [                // Architecture doc §4 structured-output citations field
        { source_id: UUID, title: String, corpus_or_trial: "corpus"|"trial" }
      ],
      disclaimer_shown: Boolean,
      created_at: ISODate
    }
  ]
}
```

This is the audit trail for every AI Care Agent turn (Architecture doc §4 "logged, full tool-call trace"). `tool_calls` + `citations` together are what a compliance review reads to verify the output validator actually enforced citation-per-claim — this collection is the evidence, not just a chat log.

**Retention:** subject to the same deletion-request rules as everything else (§6) — a patient data-deletion request must purge or anonymize this collection too, not just the Postgres/Timescale rows.

---

## 5. Vector DB Reference Table (PostgreSQL, bridges to §1's vector store)

```sql
CREATE TABLE corpus_sources (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disease_profile_id UUID NOT NULL REFERENCES disease_profiles(id),
    title              TEXT NOT NULL,
    source_type        TEXT NOT NULL CHECK (source_type IN ('pubmed_abstract', 'clinical_guideline', 'patient_forum_consented')),
    clinician_reviewed  BOOLEAN NOT NULL DEFAULT false,   -- backs the "clinician-reviewed" badge, Product/UX doc §4
    url                TEXT,
    vector_id          TEXT NOT NULL,   -- ID in the vector DB (pgvector row or Pinecone vector ID)
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`search_corpus` tool implementation: query the vector store scoped to `disease_profiles.corpus_namespace`, then join matched `vector_id`s back to this table for the citation metadata (title, URL, `clinician_reviewed` flag) the Care Agent's structured output needs.

---

## 6. Data Retention & Deletion (PRD §8, GDPR/HIPAA)

- **Soft delete first:** every PHI-bearing table has (or inherits via cascade) a `deleted_at`-style marker or is covered by a patient-scoped purge job — patients/caregivers tables directly; hypertables purge by `patient_id` on request rather than per-row soft-delete (time-series soft-delete at row grain doesn't scale).
- **Deletion request flow:** on a verified request, a single job (a) hard-deletes all hypertable rows for that `patient_id`, (b) hard-deletes the Mongo `agent_conversations` matching that `patient_id`, (c) marks the Postgres `patients` row `deleted_at` and scrubs any directly-identifying fields left, (d) writes one audit-log entry recording the deletion itself (§7) — the audit log entry survives the deletion by design, it's the record that deletion happened, not PHI itself.
- **Consent revocation ≠ deletion.** Revoking `research_personalization` consent (§2.4) stops future use, doesn't retroactively delete past data — different action, different button in the UI, don't conflate them.

---

## 7. Audit Log (PRD §8 — audit-ready from day 1)

```sql
CREATE TABLE audit_log (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_type   TEXT NOT NULL CHECK (actor_type IN ('patient', 'caregiver', 'system', 'ai_agent')),
    actor_id     UUID,                 -- null for actor_type = 'system'
    action       TEXT NOT NULL,        -- e.g. 'record_accessed', 'consent_revoked', 'data_deleted', 'alert_acknowledged'
    resource_type TEXT NOT NULL,
    resource_id   UUID,
    metadata      JSONB,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
SELECT create_hypertable('audit_log', 'occurred_at');
```

**This table is append-only at the application layer (no UPDATE/DELETE grants) and lives in a separate logical schema from operational data** — per Architecture doc §3's explicit requirement that audit logs not share retention/access policy with general app data. A caregiver viewing a patient's dashboard, an AI agent tool call touching patient data, and a deletion request all write here.

---

## 8. Row-Level Access (maps to Architecture doc §3 RBAC)

Enforced primarily at the service layer (API Gateway/Auth, Architecture doc §3), not Postgres RLS policies in MVP — RLS is a defense-in-depth candidate for phase 2, not required for launch, since the service layer is the single write/read path and already scopes every query by the authenticated `patient_id`/`caregiver_id`. Documented here so the two layers don't silently diverge:

- **Patient session** → can read/write only rows where `patient_id = self`.
- **Caregiver session** → can read (never write clinical data) rows for `patient_id`s with an active `patient_caregiver_links` row for that caregiver. Cannot read `agent_conversations` content (PRD: Care Agent is patient-facing; caregiver sees adherence/alerts/trends, not the patient's private conversation transcript, unless the patient explicitly shares it — no such sharing feature in MVP).
- **AI Care Agent tool calls** (`get_patient_record`, `get_checkin_history`) → scoped to the requesting patient's own `patient_id` only, enforced at the tool-implementation layer per Architecture doc §4 ("no tool returns another patient's data").

---

## 9. Open Items

1. **Vector DB choice** (pgvector vs. Pinecone, Architecture doc §8 open decision) — `corpus_sources.vector_id` schema works either way, but pgvector would collapse §1's four-store split to three.
2. **Wearable webhook payload schema** for `symptom_events.sensor_payload` — depends on Architecture doc §8's wearable partner decision (Apple HealthKit vs. dedicated medical wearable); JSONB column is deliberately unstructured until that's picked.
3. **Index/partition tuning** (chunk interval, compression policy specifics) — deferred to implementation; the hypertable choices above are the schema-level decision, not the ops tuning.

---

*Next: Testing strategy (05-Testing) — adversarial AI-safety tests for the Care Agent pipeline (Architecture doc §4), accessibility testing (Product/UX doc §2), and compliance audit checklist against this schema's consent/deletion/audit-log design.*
