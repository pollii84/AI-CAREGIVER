# AI Caregiver — Backend

FastAPI service implementing [02-Software-Architecture](../02-Software-Architecture/ARCHITECTURE.md) and [04-Database](../04-Database/DATABASE_DESIGN.md). MVP scope, Parkinson's only, per [01-PRD](../01-PRD/PRD.md).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Set ANTHROPIC_API_KEY, or leave unset and run `ant auth login` — the
# Anthropic SDK resolves credentials from that profile automatically.

docker compose up -d          # Postgres+Timescale (schema auto-applied on first boot) + Mongo
uvicorn app.main:app --reload
```

API docs at `http://localhost:8000/docs`.

## What's here

- `app/db/models/` — SQLAlchemy models mirroring `db/schema.sql`, which mirrors [04-Database](../04-Database/DATABASE_DESIGN.md) exactly.
- `app/agent/` — the Care Agent pipeline (Architecture doc §4): intent classifier (emergency bypass), tool set (`get_patient_record`, `search_corpus`, `search_trials`, `get_checkin_history`), Claude Sonnet 5 tool-use loop, structured-output schema, application-layer output validator.
- `app/mongo/conversations.py` — `agent_conversations` collection (Database doc §4.1), the Care Agent's audit trail.
- `app/api/v1/` — REST endpoints for patients, medications, check-ins, and the Care Agent chat.

## Known gaps (tracked, not silently missing)

- **No auth layer yet.** Every route trusts `patient_id` from the URL path. Architecture doc §3 specifies OAuth2+JWT+RBAC — until that's built, do not deploy this past local dev. Each route with a gap is marked `TODO(auth)`.
- **`search_corpus` is a stub.** ILIKE text search over `corpus_sources` metadata, not real semantic retrieval — blocked on Architecture doc §8's open vector-DB decision (pgvector vs. Pinecone). Citation shape is final; retrieval implementation isn't.
- **UPDRS/CDR/EDSS scoring is not implemented.** `checkins.computed_score` is caller-supplied for now; real scoring from `disease_profiles.rating_scale_config` is a TODO in `app/api/v1/checkins.py`.
- **No caregiver alert delivery.** `alerts` rows are written (emergency path, `app/agent/pipeline.py`) but nothing dispatches push/SMS yet — Architecture doc §3's Notification Service (Twilio) isn't scaffolded.
- **No reminder-firing job.** `medications.schedule_rrule` is stored but nothing reads it on a schedule yet.
- **No adversarial test suite.** Testing doc §2.1 describes the categories; `tests/` here is a placeholder. Do not treat this backend as safety-validated until that suite exists and passes.
- **Mongo/Postgres mixed sync-in-async.** Tool implementations (`app/agent/tools.py`) run sync SQLAlchemy queries inside async pipeline code — fine for scaffold/dev load, flagged for a production pass (async SQLAlchemy engine or `run_in_executor`).

## Design-system-to-schema anchors

If you're picking this up cold: `disease_profiles` is the single pluggability point (Architecture doc §5) — Alzheimer's/MS come online by inserting/activating a row here, not by branching code. Check `db/schema.sql`'s seed insert for the Parkinson's row shape, including the AI Behavior Contract text (PRD §AI Behavior Contract) stored verbatim as the system prompt.
