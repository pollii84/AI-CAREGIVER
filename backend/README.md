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
#
# JWT keypair: leave JWT_*_PEM/JWT_*_PATH unset for local dev — the first
# request that needs to sign or verify a token auto-generates an RS256
# keypair under .keys/ (gitignored) and reuses it on subsequent requests
# within the same checkout. See .env.example for the prod/CI alternative
# (inline PEM via secrets manager) and Known gaps below for the tradeoff.

docker compose up -d          # Postgres+Timescale (schema auto-applied on first boot) + Mongo
uvicorn app.main:app --reload
```

API docs at `http://localhost:8000/docs`.

**Schema changes require a re-init**, since `db/schema.sql` only runs on first boot of the Postgres volume: `docker compose down -v && docker compose up -d`.

## What's here

- `app/db/models/` — SQLAlchemy models mirroring `db/schema.sql`, which mirrors [04-Database](../04-Database/DATABASE_DESIGN.md) exactly.
- `app/agent/` — the Care Agent pipeline (Architecture doc §4): intent classifier (emergency bypass), tool set (`get_patient_record`, `search_corpus`, `search_trials`, `get_checkin_history`), Claude Sonnet 5 tool-use loop, structured-output schema, application-layer output validator.
- `app/mongo/conversations.py` — `agent_conversations` collection (Database doc §4.1), the Care Agent's audit trail.
- `app/api/v1/` — REST endpoints for auth, caregiver invites, patients, medications, check-ins, and the Care Agent chat.
- `app/auth/` — password hashing (Argon2id), RS256 keypair loading/generation, access/refresh token issuance, invite helpers — the issuance/business-logic half of the auth layer ([02-Software-Architecture/AUTH_LAYER.md](../02-Software-Architecture/AUTH_LAYER.md)).
- `app/core/security.py` — the verification half: `Identity`/`ScopedIdentity` dataclasses and the `Depends()` chain (`get_current_identity` → `require_patient_scope` / `require_patient_write_scope` / `require_patient_self`) that routes use to enforce who can touch which `patient_id`. `require_patient_self` (Care Agent routes only) never accepts a caregiver, however active their link — Database doc §8.

## Known gaps (tracked, not silently missing)

- **`search_corpus` is a stub.** ILIKE text search over `corpus_sources` metadata, not real semantic retrieval — blocked on Architecture doc §8's open vector-DB decision (pgvector vs. Pinecone). Citation shape is final; retrieval implementation isn't.
- **UPDRS/CDR/EDSS scoring is not implemented.** `checkins.computed_score` is caller-supplied for now; real scoring from `disease_profiles.rating_scale_config` is a TODO in `app/api/v1/checkins.py`.
- **No caregiver alert delivery, including invite delivery.** `alerts` rows are written (emergency path, `app/agent/pipeline.py`) but nothing dispatches push/SMS yet — Architecture doc §3's Notification Service (Twilio) isn't scaffolded. Same gap now also applies to caregiver invites: `POST /patients/{id}/caregiver-invites` returns the raw invite token directly in the response body (`invite_token`) instead of emailing/texting it, since there's no delivery mechanism to hand it to. Fine for local dev/testing; must be fixed (token sent out-of-band only, not returned to the caller) before this is anything but local dev.
- **No reminder-firing job.** `medications.schedule_rrule` is stored but nothing reads it on a schedule yet.
- **No adversarial test suite.** Testing doc §2.1 describes the categories; `tests/` here is a placeholder. Do not treat this backend as safety-validated until that suite exists and passes. This now includes the auth layer's own failure modes (AUTH_LAYER.md §9 step 11) — verified manually live (see that doc's implementation, and the commit that added it) but not yet codified as an automated regression suite.
- **Mongo/Postgres mixed sync-in-async.** Tool implementations (`app/agent/tools.py`) run sync SQLAlchemy queries inside async pipeline code — fine for scaffold/dev load, flagged for a production pass (async SQLAlchemy engine or `run_in_executor`). The new auth routes (`app/api/v1/auth.py`, `caregiver_invites.py`) are sync-only (no async DB calls), consistent with the rest of `app/api/v1/` — not a new instance of this gap, just noting it doesn't get better or worse here.
- **Dev-mode JWT keypair persistence.** `app/auth/keys.py` auto-generates an RS256 keypair to `.keys/` (gitignored) the first time none is configured. Every server restart *before* that file exists on disk mints a new keypair, invalidating every previously-issued token — acceptable for a single local checkout (the file persists across restarts once created) but would break multi-instance or ephemeral-filesystem deployments; those need real key material via `JWT_PRIVATE_KEY_PEM`/`JWT_PUBLIC_KEY_PEM` (see `.env.example`).
- **No rate limiting or account lockout on failed logins.** AUTH_LAYER.md §2.2 explicitly leaves this as a Backend Dev implementation detail rather than re-specifying it; it's not built. Failed logins do write to `audit_log` (`action='login_failed'`) so brute-force patterns are at least visible after the fact, but nothing currently blocks or throttles the attempts.
- **No email verification enforcement.** `patient_credentials.email_verified` / `caregiver_credentials.email_verified` exist per AUTH_LAYER.md §8.1 but nothing sends a verification email or gates login/invite-acceptance on the flag — it stays `false` for every row.
- **No display name anywhere in the schema.** `patients`/`caregivers`/their credentials tables carry no name field (Database doc §2.1's "not duplicated here" note, extended to the new credentials tables — only email lives there). `GET /caregiver-invites/{token}` therefore can't show the invitee any human-readable "invited by ___" context — it returns `patient_id` only. AUTH_LAYER.md §6.2 flags this as a Product/UX doc gap, not something to invent here.
- **`clinician` link role has no permission difference from `family`.** Both get identical read-only access via `require_patient_scope` — AUTH_LAYER.md §4 notes this is deliberate (phase-2 scope), not an oversight.
- **Password policy is Argon2id hashing only** — no minimum length/complexity check beyond what the client sends. AUTH_LAYER.md §2.2 leaves this as an implementation detail, not re-specified there either.

## Design-system-to-schema anchors

If you're picking this up cold: `disease_profiles` is the single pluggability point (Architecture doc §5) — Alzheimer's/MS come online by inserting/activating a row here, not by branching code. Check `db/schema.sql`'s seed insert for the Parkinson's row shape, including the AI Behavior Contract text (PRD §AI Behavior Contract) stored verbatim as the system prompt.
