# Auth Layer — AI Caregiver for Neurodegenerative Patients

**Status:** Draft v0.1 — spec, not yet implemented
**Depends on:** [01-PRD/PRD.md](../01-PRD/PRD.md), [02-Software-Architecture/ARCHITECTURE.md](../02-Software-Architecture/ARCHITECTURE.md) §3 (Layer-by-Layer Decisions — Auth row), [04-Database/DATABASE_DESIGN.md](../04-Database/DATABASE_DESIGN.md) §2.1, §8, [backend/README.md](../backend/README.md) — Known gaps
**Last updated:** 2026-07-03

---

## 0. Why this doc exists

Architecture doc §3 specifies "OAuth2 + JWT, RBAC with `patient`, `caregiver`, `clinician` roles" and "integrate with existing health-ID providers" but never details the mechanism. backend/README.md's Known gaps section names the consequence directly: **every route trusts `patient_id` from the URL path**, marked `TODO(auth)` throughout `app/api/v1/*.py`. This doc closes that gap with a concrete, buildable spec. It does not touch application code — see §9 for the implementation checklist a Backend Dev works from.

---

## 1. Decision Summary

| Question | Decision | Why (brief — detail in the referenced section) |
|---|---|---|
| Federated health-ID login (PRD Integration Points, Apple HealthKit) at launch? | **No.** Local email+password auth, MVP. | HealthKit is a sensor/wearable data API (fall detection, PRD Open Risk #3) — it has no "Sign in with HealthKit" identity flow. It was never a real login-federation candidate; conflating it with auth in the PRD's Key Decision was the actual gap. See §2. |
| Migration path to federated/health-ID login later? | Yes — credentials table is provider-shaped from day one (`provider` + `external_subject_id` columns, currently always `'local'`). | Adding a provider later is a data-model no-op, not a schema rewrite. See §2.3. |
| JWT signing algorithm | RS256 (asymmetric) | Architecture doc §2 diagram draws "API Gateway / Auth" as a component other services (Notification Service, AI Inference Orchestrator) sit alongside, not necessarily inside — asymmetric signing means only the Auth component holds the private key; anything that only needs to verify tokens gets the public key. Cheap insurance if any of those become separate deployables. |
| Access token | Short-lived JWT (15 min), stateless | Standard; short window bounds the blast radius of a leaked access token. |
| Refresh token | Long-lived (30 days), **opaque random token, not a JWT**, stored server-side hashed, rotated on every use | Needs to be revocable (logout, compromised device, caregiver link revoked) — a stateless JWT refresh token can't be invalidated before its own expiry without a denylist, which is just a worse version of a server-side token table. See §3.2. |
| Caregiver → patient scoping mechanism | **Live DB lookup against `patient_caregiver_links` on every request**, not a patient-ID list embedded in the JWT at login | `patient_caregiver_links.status` exists specifically so access can be revoked (Database doc §2.1). A JWT with an embedded patient list would keep authorizing a revoked caregiver until that access token's 15-minute expiry — acceptable staleness for some systems, not for "caregiver alert" access to a Parkinson's patient's data. Correctness over one extra indexed query. See §5. |
| Care Agent conversation routes | **Patient-actor-only**, never satisfied by a caregiver link, however active | Database doc §8 is explicit: caregivers see adherence/alerts/trends, never the patient's private Care Agent transcript, with no sharing feature in MVP. This needs its own dependency, distinct from the generic "caller may access this patient_id" one used elsewhere — see §6. |
| New DB tables/columns | Yes — enumerated in §8 | Nothing in the current schema stores a credential, a refresh token, or a caregiver invite. |

---

## 2. Identity Provider Decision

### 2.1 Why local auth, and why this isn't deferring a decision that was actually already answered

PRD Open Risks/Decisions #3 frames "sensor/wearable partner (Apple HealthKit vs. dedicated medical wearable)" as the open item — that's about **fall-detection data ingestion** (Architecture doc §6: `Wearable sensor → HealthKit/vendor API → webhook to Service Layer`), a deterministic alert pipeline with no LLM and no bearing on login. Apple HealthKit does not offer an identity/SSO surface an app can authenticate a user against. There is no "existing health-ID provider" in the PRD's own reference material that functions as an OAuth identity provider today. Treating "integrate with health-ID providers" as an unresolved *login* mechanism was the actual gap — closed here by observing it was never a real fork: build local auth now, structure it so a future federated provider (a genuine health-ID SSO product, a hospital system's IdP, Sign in with Apple as a generic — non-HealthKit — identity option) can be added later without a redesign.

### 2.2 What "local auth" means here

Email + password for both patients and caregivers. Password hashing: **Argon2id** (via `argon2-cffi`), not bcrypt — no 72-byte input truncation footgun, tunable memory cost, current OWASP recommendation. Minimum password policy and account lockout/rate-limiting on failed logins are implementation details for the Backend Dev, not re-specified here, but failed-login attempts must write to `audit_log` (§8.4) so brute-force patterns are visible in the same audit trail as everything else (PRD §Compliance & Security — audit-ready access logs).

### 2.3 Migration path (so this isn't a dead end)

The credentials tables (§8.1) carry:

```
provider              TEXT NOT NULL DEFAULT 'local'   -- 'local' | future: 'apple_health_id' | 'hospital_idp' | ...
external_subject_id   TEXT                              -- null for 'local'; the provider's user ID once one exists
password_hash         TEXT                              -- null when provider != 'local'
```

Adding a federated provider later means: add an OAuth2 authorization-code flow that, on success, either finds an existing row by `(provider, external_subject_id)` or creates one, then issues this system's own JWT exactly as §3 describes — the rest of the auth layer (token shape, `Depends()` pattern, caregiver scoping) is unchanged. This is the same "config/data, not code branching" discipline Architecture doc §5 applies to disease profiles, applied here to identity providers.

---

## 3. Token Strategy

### 3.1 Access token (JWT)

Claims:

```json
{
  "sub": "6f1a2e3c-...",        // patients.id if actor_type=patient, caregivers.id if actor_type=caregiver
  "actor_type": "patient",       // "patient" | "caregiver" — mirrors audit_log.actor_type (Database doc §7)
  "token_type": "access",
  "sid": "3c9e...",              // session id — ties this access token to the refresh-token chain that issued it (§3.2)
  "iat": 1751500000,
  "exp": 1751500900               // iat + 15 min
}
```

Deliberately **not** in the claims:
- **`role`** — role (`family`/`clinician`) lives on `patient_caregiver_links`, per-link, not per-caregiver-account. A caregiver could in principle have different roles across different patient links (schema allows it even though MVP doesn't build multi-caregiver UI — Database doc §2.1 note). Putting a single global `role` in the token would be modeling a fact that isn't actually global to the actor. Role is resolved per-request, per-patient, from the DB (§5).
- **A list of accessible `patient_id`s** — see §5, this is the revocation-latency issue.

`sub` is deliberately the same UUID as the `patients.id` / `caregivers.id` row, not a separate "user id" — see §7.1 for why, and note this is a departure from a strict reading of Database doc §2.1 ("name, DOB, contact info live in the auth/identity provider... not duplicated here"): that note was written assuming full identity federation. Under local auth, the *account* record (email + password_hash) still lives in a separate credentials table outside `patients`/`caregivers` (§8.1), preserving the spirit of the note — clinical/app tables don't carry login secrets or contact info — even though the ID itself is now shared rather than mapped.

Signing: RS256, private key held only by the auth-issuing code path, public key distributed to anything that verifies (currently just this one FastAPI service, but see §1's asymmetric-signing rationale). Key material via env/secrets manager (matches `settings.anthropic_api_key` pattern in `app/core/config.py`) — `jwt_private_key_pem`, `jwt_public_key_pem`, plus a `kid` claim once key rotation is needed (not MVP-blocking, but the claim slot should exist from day one so rotation isn't a breaking change later).

### 3.2 Refresh token

Opaque, high-entropy random token (32 bytes, base64url), **not** a JWT — it carries no claims itself, it's a lookup key. Server stores only its SHA-256 hash (never the raw token) in a `refresh_tokens` table (§8.2), alongside `actor_type`, `actor_id`, `session_id` (the `sid` from §3.1), `expires_at`, `revoked_at`, and `replaced_by_id` for rotation chaining.

- **Rotation on every use:** each call to `POST /api/v1/auth/refresh` consumes the presented refresh token, issues a new access token *and* a new refresh token, and marks the old refresh-token row `replaced_by_id = <new row id>`.
- **Reuse detection:** if a refresh token whose row already has `replaced_by_id` set is presented again, that's a signal of token theft (the legitimate client already rotated past it) — revoke the entire `session_id` chain, not just that token, and write an `audit_log` entry (`action = 'refresh_token_reuse_detected'`).
- **Where it lives client-side:**
  - Caregiver Portal (React web, Architecture doc §3): **httpOnly, Secure, SameSite=Strict cookie**, scoped to the API domain. Never touched by JS — mitigates XSS token theft.
  - Patient app (React Native, no first-class httpOnly-cookie story on mobile): device secure storage (iOS Keychain / Android Keystore via a library like `react-native-keychain`), sent explicitly in the `POST /auth/refresh` request body. This is the standard mobile pattern; cookie-based storage doesn't transfer cleanly to React Native's networking stack.
- **Logout:** `POST /api/v1/auth/logout` revokes the current session's refresh-token row (`revoked_at = now()`); access tokens already issued remain valid until their own 15-minute expiry (acceptable — this is the standard access/refresh tradeoff, and 15 minutes is short by design).

### 3.3 `Depends()` pattern — from `Authorization: Bearer <token>` to verified identity

Fits alongside the existing `Depends(get_db)` style in `app/db/base.py`. New module `app/core/security.py`:

```python
# app/core/security.py
from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    actor_id: UUID          # == patients.id or caregivers.id, per actor_type
    actor_type: str         # "patient" | "caregiver"
    session_id: UUID        # JWT "sid" claim


def get_current_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Identity:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_public_key_pem,
            algorithms=["RS256"],
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    if payload.get("token_type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not an access token")

    return Identity(
        actor_id=UUID(payload["sub"]),
        actor_type=payload["actor_type"],
        session_id=UUID(payload["sid"]),
    )
```

This is the base dependency. §5 and §6 build patient-scoping and agent-scoping dependencies on top of it — routes don't call `get_current_identity` directly except at `/auth/*` endpoints that don't take a `patient_id` path param.

---

## 4. Role Model

Roles come straight from what's already in the DB — **no parallel role system is introduced**:

- `patient` — an `actor_type` value (matches `audit_log.actor_type`, Database doc §7). A patient identity is always scoped to exactly one `patients.id` (itself).
- `caregiver` (family) / `clinician` — these are the two allowed values of `patient_caregiver_links.role` (Database doc §2.1), scoped **per link**, not per caregiver account. `clinician` is phase 2 per that table's own comment; the mechanism below already supports it since it reads the `role` column generically. MVP authorization logic does not branch on `role` value (both `family` and `clinician` links get the same read-only access) — same "don't special-case in code, let it be data" discipline Architecture doc §5 applies to disease branching. A future phase-2 permission difference (e.g., clinician write access to a care plan) is a change to the authorization check's `role`-based branch, not a new role system.

### 4.1 Caregiver → patient scoping mechanism

This is the concrete answer to Database doc §8's stated intent ("caregiver session can read... rows for `patient_id`s with an active `patient_caregiver_links` row"):

```python
# app/core/security.py (continued)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import PatientCaregiverLink


@dataclass(frozen=True)
class ScopedIdentity:
    patient_id: UUID
    actor_type: str          # "patient" | "caregiver"
    actor_id: UUID
    link_role: str | None    # "family" | "clinician" | None (None when actor_type == "patient")


def require_patient_scope(
    patient_id: UUID,
    identity: Identity = Depends(get_current_identity),
    db: Session = Depends(get_db),
) -> ScopedIdentity:
    if identity.actor_type == "patient":
        if identity.actor_id != patient_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this patient")
        return ScopedIdentity(patient_id=patient_id, actor_type="patient", actor_id=identity.actor_id, link_role=None)

    if identity.actor_type == "caregiver":
        link = db.scalar(
            select(PatientCaregiverLink).where(
                PatientCaregiverLink.caregiver_id == identity.actor_id,
                PatientCaregiverLink.patient_id == patient_id,
                PatientCaregiverLink.status == "active",
            )
        )
        if link is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No active link to this patient")
        return ScopedIdentity(
            patient_id=patient_id, actor_type="caregiver", actor_id=identity.actor_id, link_role=link.role
        )

    raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown actor type")
```

Because `patient_id` is declared as a plain parameter on this dependency function, FastAPI resolves it from the path — same mechanism the route functions already use. A route adds one line:

```python
# app/api/v1/checkins.py — before/after
@router.get("", response_model=list[CheckinOut])
def list_checkins(
    patient_id: UUID,
    db: Session = Depends(get_db),
    _scope: ScopedIdentity = Depends(require_patient_scope),   # + this line
):
    ...
```

The query itself (`Checkin.patient_id == patient_id`) doesn't need to change — `patient_id` was already the trusted value once `require_patient_scope` has run without raising. This is a live query (`patient_caregiver_links` lookup) on every caregiver request, not a cached/embedded list — see §1's Decision Summary row for why that's deliberate. If this becomes a measurable hot path later, a short-TTL (e.g. 30–60s) cache keyed on `(caregiver_id, patient_id)` is a reasonable optimization — not needed for MVP traffic, and any cache TTL directly reintroduces the revocation-latency tradeoff being avoided here, so keep it short if added.

Patient-actor write routes (medications, checkins) should additionally reject caregiver writes at the route level ("caregiver session... never write clinical data," Database doc §8) — `require_patient_scope` alone doesn't enforce read vs. write, so POST routes need `if _scope.actor_type != "patient": raise HTTPException(403, ...)` (or a `require_patient_actor_only` variant of the dependency) in addition to scoping. Call this out explicitly in the handoff checklist (§9) since it's easy to wire the read-scoping dependency onto a write route and assume that's sufficient.

---

## 5. Care Agent Integration — identity flowing into `app/agent/tools.py`

This is the piece the task specifically flags: right now `patient_id` reaches `get_patient_record`, `search_corpus`, `get_checkin_history` etc. as a plain function argument threaded down from the HTTP path param, with the tool-implementation-layer rule ("no tool returns another patient's data") resting entirely on that argument being trustworthy. It becomes actually enforced, not just conventionally true, once the value handed to `run_care_agent_turn` is the output of an auth dependency rather than a raw path param.

### 5.1 Agent routes need a stricter dependency than §4.1's generic one

Database doc §8: "Cannot read `agent_conversations` content... Care Agent is patient-facing; caregiver sees adherence/alerts/trends, not the patient's private conversation transcript... no such sharing feature in MVP." `require_patient_scope` (§4.1) would *incorrectly* let a linked caregiver hit `/patients/{patient_id}/agent/*`, because an active caregiver link is sufficient for that dependency by design (it's meant to be, for checkins/medications). The agent router needs its own dependency that only ever accepts a patient actor:

```python
def require_patient_self(
    patient_id: UUID,
    identity: Identity = Depends(get_current_identity),
) -> UUID:
    if identity.actor_type != "patient" or identity.actor_id != patient_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Care Agent access is patient-only")
    return identity.actor_id   # == patient_id; see 5.2 for why the dependency returns this, not the raw path value
```

### 5.2 Threading the verified ID down through the pipeline

```python
# app/api/v1/agent.py — before/after
@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
async def send_message(
    conversation_id: str,
    payload: MessageIn,
    db: Session = Depends(get_db),
    verified_patient_id: UUID = Depends(require_patient_self),   # replaces bare `patient_id: UUID`
):
    result = await run_care_agent_turn(
        db=db,
        patient_id=verified_patient_id,     # server-verified value, not the raw path param
        conversation_id=conversation_id,
        user_message=payload.message,
    )
    return result
```

The important detail: `run_care_agent_turn(..., patient_id=...)` now receives the dependency's return value, not the route's own `patient_id` path binding. Both are equal by the time `require_patient_self` has returned without raising, but passing the dependency's output is the pattern that keeps this true by construction rather than by the two happening to agree — if a future refactor adds another route to this router that takes a `patient_id` from a request body instead of the path (e.g. a batch endpoint), the dependency-sourced value can't silently diverge from what was authorized the way a second independently-read path param could.

From there, nothing in `app/agent/pipeline.py` or `app/agent/tools.py` needs to change. `patient_id` was already threaded from `run_care_agent_turn`'s parameter down into every tool call (`impl(db, patient_id, block.input)` in `pipeline.py`); tools already ignore any patient/model-supplied ID (per `tools.py`'s own docstring — "Each function below takes `patient_id` from the authenticated session, never from the model's tool-call input"). That docstring's claim becomes true the moment the caller (`agent.py`) is guaranteed to only ever pass an authenticated, patient-actor-owned ID — which is exactly what §5.1's dependency guarantees and what was previously missing. **The fix is entirely at the route boundary; the tool-implementation layer was already written correctly, it just had no trustworthy input.**

### 5.3 `start()` needs the same fix

`start_conversation` currently takes a bare `patient_id: UUID` with no `Depends()` at all (`app/api/v1/agent.py` line 30) — apply the identical `require_patient_self` dependency there.

---

## 6. Onboarding & Invite Flows

Neither 01-PRD nor 03-Product-UX-Design-Frontend specifies who initiates a caregiver invite or the account-creation UX in implementation detail (checked directly — Product/UX doc covers the caregiver portal's dashboard views, not the invite mechanism); this section is the first place that gets specified, not a restatement of an existing design.

### 6.1 New patient — no account yet

```
1. Patient opens app -> "Create account" -> POST /api/v1/auth/register/patient
   { email, password, disease_code, preferred_comm_mode }
2. Server, in one transaction:
   a. INSERT patient_credentials (email, password_hash, provider='local')
   b. INSERT patients (disease_profile_id resolved from disease_code, preferred_comm_mode)
      -- using the SAME id for both rows (patients.id generated first, credentials
      -- row keyed on it) -- see §7.1 for why sub == patients.id
   c. audit_log: actor_type='patient', action='account_created'
3. Server issues access + refresh token pair (§3), returns them + patient_id.
4. Client proceeds into the existing onboarding UX (PRD Entry Point & FTUE —
   diagnosis entry, medication list, consent capture) now authenticated.
```

This **replaces** the current standalone `POST /patients` endpoint's role as the entry point — that endpoint's logic (disease-profile lookup, row creation) moves into `register/patient`'s transaction. Whether the old route is deleted or kept as an internal-only helper called by the new one is an implementation call for the Backend Dev; it should not remain reachable unauthenticated at its current path.

Login: `POST /api/v1/auth/login` `{email, password}` → verify against `patient_credentials` or `caregiver_credentials` (try both, or take an explicit `actor_type` hint from the client if the login screens are already separate per PRD "Caregiver Experience: Separate login") → issue token pair.

### 6.2 Caregiver invite — who initiates, and how

**The patient initiates.** MVP has no admin/clinician back-office and multi-caregiver support is explicitly Future/Fast-Follow (PRD), so there's no other actor positioned to originate a link. This also matches `patient_caregiver_links` already being scoped by `patient_id` first.

```
1. Patient (already authenticated), from their app:
   POST /api/v1/patients/{patient_id}/caregiver-invites
   { email, role: "family" }        -- "clinician" not exposed in MVP UI per
                                     -- Database doc §2.1's phase-2 note, though
                                     -- the mechanism below doesn't care which
                                     -- role string is passed
   Guarded by require_patient_scope + actor_type == "patient" (§4.1's write-route rule).

2. Server: INSERT caregiver_invites (patient_id, email, role, token=<opaque>,
   status='pending', expires_at=now()+7d). Send invite email/SMS (Twilio,
   Architecture doc §3) with a link containing the token. audit_log:
   actor_type='patient', action='caregiver_invited'.

3. Invitee clicks link -> app/portal shows "Accept invite":
   GET /api/v1/caregiver-invites/{token}  (no auth required -- token IS the auth for this one lookup)
   -> shows inviting patient context (first name only, or whatever minimal
      context the Product/UX flow wants -- not specified here, flag for that doc)

4. Two branches, both converging on the same step-5 transaction — the accept
   logic runs exactly once either way, just triggered from a different call:

   **4a. No caregiver account yet:**
   `POST /api/v1/auth/register/caregiver { email, password, invite_token }`
   — this single call performs the full step-5 transaction below inline
   (credentials insert *and* link creation together). There is no separate
   client-side call to `/accept` in this branch; the token param is what
   tells the registration endpoint to also do the accept work.

   **4b. Caregiver already has an account:**
   `POST /api/v1/auth/login`, then a separate
   `POST /api/v1/caregiver-invites/{token}/accept` (authenticated) — step 5
   runs here instead, minus the credentials-insert (already exists).

5. Accept step, server-side, one transaction (invoked from 4a or 4b):
   a. Validate token: status='pending', not expired. Email-match check
      differs by branch since 4a has no session yet to check against:
      - **4a:** the registration payload's `email` must equal the invite's
        `email` (case-insensitive) — reject with 400 otherwise, before
        creating any row, so a token can't be redeemed under a different
        email than it was sent to.
      - **4b:** the authenticated caregiver's `caregiver_credentials.email`
        must equal the invite's `email`.
   b. (4a only) INSERT caregiver_credentials (email, password_hash, provider='local').
   c. INSERT patient_caregiver_links (patient_id, caregiver_id, role, status='active').
   d. UPDATE caregiver_invites SET status='accepted', accepted_at=now().
   e. audit_log: actor_type='caregiver', action='caregiver_link_accepted'
      (plus 'account_created' too, for the 4a branch).
   f. Issue token pair for the caregiver.
```

Revocation: `DELETE /api/v1/patients/{patient_id}/caregivers/{caregiver_id}` (patient-only, per §4.1's write-route rule) sets `patient_caregiver_links.status='revoked'`, `revoked_at=now()`. Because §4.1's scoping check is a live query, this takes effect on the caregiver's *next request* — no separate token-invalidation step needed, which is the direct payoff of the live-lookup decision in §1.

---

## 7. Why `sub` == the app-table row ID (ties §3.1 and §6.1 together)

### 7.1

An alternative design keeps auth identity fully separate — a `users` table with its own UUID, mapped 1:1 to `patients.id` via a foreign key. That's a more conventional "identity provider" shape and is what Database doc §2.1's phrasing ("name, DOB, contact info live in the auth/identity provider... not duplicated here") reads as anticipating — written with a *fully external* IdP in mind (a real OAuth provider issuing its own opaque subject IDs the app maps against). Under local auth, that provider is this codebase, not an external system, so introducing a second ID and a mapping table buys no real decoupling — it's an extra join on every request for no independent benefit, since both tables live in the same Postgres database and deploy together. Using the same ID for both keeps `require_patient_scope`, the Care Agent tool calls, and every `WHERE patient_id = ...` query in the codebase today unchanged in shape. If a genuine external IdP is added later (§2.3), the credentials table's `external_subject_id` column is exactly the seam for that provider's own ID — `patients.id` doesn't need to move.

---

## 8. DB Schema Changes

New tables only — no changes to existing tables (`patients`, `caregivers`, `patient_caregiver_links` are untouched, matching Database doc §2.1's intent that identity/contact data not be duplicated into them).

### 8.1 Credentials (two tables — patient and caregiver credentials are never queried together, so no benefit to a shared/polymorphic table)

```sql
CREATE TABLE patient_credentials (
    patient_id      UUID PRIMARY KEY REFERENCES patients(id),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT,                     -- null when provider != 'local'
    provider        TEXT NOT NULL DEFAULT 'local',
    external_subject_id TEXT,                 -- null for 'local'; §2.3
    email_verified  BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE caregiver_credentials (
    caregiver_id    UUID PRIMARY KEY REFERENCES caregivers(id),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT,
    provider        TEXT NOT NULL DEFAULT 'local',
    external_subject_id TEXT,
    email_verified  BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`patient_id`/`caregiver_id` as the primary key (not a separate `id` column) enforces the §7.1 one-account-per-patient-row design at the schema level.

`email_verified` is not enforced anywhere in MVP — no flow gates login or invite-acceptance on it, and nothing currently sets it `true`. The column exists so a future verification-email step (send link on registration, flip the flag on click) is an additive change, not a migration; until then it stays `false` for every row and callers should not branch on it.

### 8.2 Refresh tokens

```sql
CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL,             -- groups a rotation chain; == JWT "sid" claim
    actor_type      TEXT NOT NULL CHECK (actor_type IN ('patient', 'caregiver')),
    actor_id        UUID NOT NULL,
    token_hash      TEXT NOT NULL UNIQUE,       -- SHA-256 of the opaque token; raw value never stored
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    replaced_by_id  UUID REFERENCES refresh_tokens(id)
);
CREATE INDEX ON refresh_tokens (session_id);
```

### 8.3 Caregiver invites

```sql
CREATE TABLE caregiver_invites (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id),
    email           TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'family' CHECK (role IN ('family', 'clinician')),
    token_hash      TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'expired', 'revoked')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    accepted_at     TIMESTAMPTZ
);
CREATE INDEX ON caregiver_invites (patient_id);
```

### 8.4 `audit_log` — no schema change, new `action` values

`audit_log.action` is unconstrained `TEXT` already (no CHECK constraint, per `db/schema.sql`), so no migration is needed — just new values written by the auth code: `account_created`, `login_succeeded`, `login_failed`, `token_refreshed`, `refresh_token_reuse_detected`, `logout`, `caregiver_invited`, `caregiver_link_accepted`, `caregiver_link_revoked`.

---

## 9. Implementation Handoff

Ordered so each step is buildable/testable before the next depends on it.

1. **Add dependencies**: `pyjwt`, `argon2-cffi` to `backend/requirements.txt`.
2. **Config**: add `jwt_private_key_pem`, `jwt_public_key_pem`, `access_token_ttl_minutes` (default 15), `refresh_token_ttl_days` (default 30) to `app/core/config.py` (`Settings`), `.env.example`.
3. **Schema migration**: add §8.1–§8.3 tables to `backend/db/schema.sql` and corresponding SQLAlchemy models in `app/db/models/core.py`.
4. **`app/core/security.py`**: `Identity`, `ScopedIdentity`, `get_current_identity`, `require_patient_scope`, `require_patient_self`, plus a write-route variant that rejects `actor_type == "caregiver"` (§4.1's last paragraph).
5. **`app/api/v1/auth.py`** (new router): `POST /auth/register/patient`, `POST /auth/register/caregiver` (accepts an optional `invite_token` — when present, performs the §6.2 step-5 accept transaction inline, not just credential creation), `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`. Wire into `app/main.py` alongside the existing routers.
6. **`app/api/v1/patients.py`**: fold `create_patient`'s logic into `register/patient`'s transaction (§6.1); add `require_patient_scope` to `get_patient`; decide whether the bare `POST /patients` route is removed or made internal-only.
7. **`app/api/v1/checkins.py`, `medications.py`**: add `require_patient_scope` to all routes; add the caregiver-write-block check to the `POST` routes specifically (§4.1).
8. **`app/api/v1/agent.py`**: replace bare `patient_id: UUID` on both `start()` and `send_message()` with `Depends(require_patient_self)` (§5.1–§5.3); pass the dependency's return value into `run_care_agent_turn`, not the raw path param.
9. **Caregiver invite routes**: new `POST /patients/{patient_id}/caregiver-invites`, `GET /caregiver-invites/{token}`, `POST /caregiver-invites/{token}/accept`, `DELETE /patients/{patient_id}/caregivers/{caregiver_id}` (§6.2).
10. **Audit logging**: every new endpoint above writes the corresponding `audit_log` row (§8.4) — do this per-endpoint as it's built, not as a follow-up pass.
11. **Tests**: cover the specific failure modes this doc calls out — revoked caregiver link rejected on next request (not just next login), agent routes reject an otherwise-valid caregiver token, refresh-token reuse triggers session-wide revocation, patient cannot access another `patient_id` even with a structurally valid token.

**Explicitly not covered by this doc** (flag for whoever owns those docs next): the invite-acceptance UX/copy (Product/UX doc gap noted in §6), rate-limiting/lockout policy specifics, and the phase-2 question of what a `clinician`-role link is actually permitted to do differently from `family` (Database doc §2.1 notes clinician role exists but is phase 2 — this doc's mechanism supports it, doesn't design its permissions).
