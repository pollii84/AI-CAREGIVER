"""
Shared fixtures for backend/tests/ (integration/ and adversarial/).

Runs against the REAL docker-compose Postgres/Timescale + Mongo stack
(backend/README.md Setup) — nothing here is an in-memory/sqlite substitute.
The HTTP layer uses an in-process ASGI transport (httpx.ASGITransport wrapping
app.main.app) rather than requiring a separately-running `uvicorn` process:
same routes, same app.agent.pipeline code, real DB I/O — just invoked
in-process so (a) tests are deterministic in CI without a manual `uvicorn`
step, and (b) tests can monkeypatch app.agent.pipeline.client in the same
process, which the no-LLM-in-path check (tests/integration/test_emergency_path.py)
depends on.

--- AUTH MIGRATION NOTE (read before editing) -----------------------------
This suite was originally written against the pre-auth route shape (bare
`patient_id` path param, no bearer token — backend/README.md "Known gaps").
While this suite was being built, the Backend Dev's auth layer (02-Software-
Architecture/AUTH_LAYER.md) landed live, in the same session: `POST
/api/v1/patients` was removed, all routes now require
`Authorization: Bearer <access_token>`, and the Care Agent routes require a
patient-actor token specifically (AUTH_LAYER.md §5.1's `require_patient_self`).
`make_patient`/`auth_headers` below have been updated to match — this is the
"small, mechanical change" this module was structured to absorb, done once
the migration was confirmed complete and the new `patient_credentials`/
`refresh_tokens` tables were confirmed present in the running container
(verified live via `POST /api/v1/auth/register/patient` returning 201 with a
real token pair, not inferred from reading code).

Two places centralize the auth surface so a *future* change (token refresh,
a different registration shape, etc.) stays mechanical:

  1. `auth_headers()` — the ONE function that knows how to attach
     credentials to a request. Returns `{"Authorization": f"Bearer ..."}`
     for a given `TestPatient`, `{}` for none.
  2. `make_patient` — the ONE place that creates a patient for a test. Calls
     `POST /api/v1/auth/register/patient` (AUTH_LAYER.md §6.1) and stashes
     the returned access token on `TestPatient.headers`.

No test file should construct its own httpx client or its own patient-creation
call outside these fixtures.
----------------------------------------------------------------------------
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text


@pytest.fixture(scope="session")
def event_loop():
    """One event loop for the whole test session, not one per test function.

    app/mongo/client.py constructs `AsyncIOMotorClient` as a process-wide
    module singleton (imported once, not per-test). Motor's background
    SDAM/heartbeat machinery binds to whatever event loop is running the
    first time it's used; pytest-asyncio's default per-function event loop
    would tear that loop down after the first test that touches Mongo,
    breaking every subsequent test with "RuntimeError: Event loop is
    closed" (reproduced while writing this suite). A single session-scoped
    loop matches the client's actual lifetime instead of fighting it."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

from app.core.config import settings
from app.db.base import SessionLocal
from app.main import app
from app.mongo.conversations import delete_patient_conversations

API_PREFIX = "/api/v1"

HAS_ANTHROPIC_KEY = bool(settings.anthropic_api_key)

NO_LLM_SKIP_REASON = (
    "ANTHROPIC_API_KEY is not set (backend/.env) -- this probe drives a real "
    "Claude Sonnet 5 call through app/agent/pipeline.py's tool-use loop and "
    "cannot be faked without lying about the result. Set the key (or run "
    "`ant auth login`, per backend/README.md Setup) and re-run to get real "
    "coverage of this category."
)


@dataclass
class TestPatient:
    id: UUID
    # TODO(auth): populate from a real access token once AUTH_LAYER.md lands
    # (see module docstring). Empty today because no auth layer exists yet.
    headers: dict = field(default_factory=dict)


def auth_headers(patient: "TestPatient | None" = None) -> dict:
    """The one seam for attaching credentials to a request. See module
    docstring — returns {} until the auth layer exists."""
    return dict(patient.headers) if patient is not None else {}


@pytest_asyncio.fixture(autouse=True)
async def _fresh_mongo_client_for_tests():
    """app/mongo/client.py builds `AsyncIOMotorClient` as a module-level
    singleton at import time — before pytest-asyncio has an event loop
    running (imports happen during collection). Motor's background SDAM
    heartbeat monitor binds to whatever loop is active the first time the
    client is used, which can end up being a different loop than the one
    that runs a given test body, producing "RuntimeError: Event loop is
    closed" / "Future ... attached to a different loop" (both reproduced
    while writing this suite, the second one even with a session-scoped
    event loop — see the `event_loop` fixture above for that half of the
    fix). Rebuilding the client fresh for EACH test function, not once per
    session, guarantees its whole lifecycle (construction, use, close) stays
    inside the one `run_until_complete` call that runs that test — no
    client instance ever crosses a test-function boundary.
    Test-infrastructure-only — does not touch application code."""
    from motor.motor_asyncio import AsyncIOMotorClient

    import app.mongo.client as mongo_client_module
    import app.mongo.conversations as conversations_module
    from app.core.config import settings

    fresh_client = AsyncIOMotorClient(settings.mongo_url)
    fresh_db = fresh_client[settings.mongo_db]
    mongo_client_module._client = fresh_client
    mongo_client_module.mongo_db = fresh_db
    conversations_module.mongo_db = fresh_db  # separate name binding, per Python import semantics
    yield
    fresh_client.close()


@pytest_asyncio.fixture
async def api() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver" + API_PREFIX) as client:
        yield client


@pytest_asyncio.fixture
async def db_conn():
    """Direct DB session for verification/cleanup — a separate connection
    from whatever session the app used to serve a request, same real
    Postgres/Timescale instance (docker-compose)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _delete_patient_rows(db_conn, patient_id: UUID) -> None:
    """No deletion-flow API exists yet (Testing doc §3 describes one;
    backend/README.md doesn't implement it) — clean up synthetic test
    patients directly, respecting FK order, so runs don't accumulate rows in
    the shared dev Postgres. Includes the new auth tables (AUTH_LAYER.md §8)
    now that patient creation goes through register/patient."""
    for stmt in (
        "DELETE FROM alerts WHERE patient_id = :pid",
        "DELETE FROM symptom_events WHERE patient_id = :pid",
        "DELETE FROM checkins WHERE patient_id = :pid",
        "DELETE FROM medication_adherence_events WHERE patient_id = :pid",
        "DELETE FROM consent_records WHERE patient_id = :pid",
        "DELETE FROM patient_caregiver_links WHERE patient_id = :pid",
        "DELETE FROM medications WHERE patient_id = :pid",
        "DELETE FROM caregiver_invites WHERE patient_id = :pid",
        "DELETE FROM refresh_tokens WHERE actor_type = 'patient' AND actor_id = :pid",
        "DELETE FROM patient_credentials WHERE patient_id = :pid",
        "DELETE FROM patients WHERE id = :pid",
    ):
        db_conn.execute(text(stmt), {"pid": str(patient_id)})
    db_conn.commit()


@pytest_asyncio.fixture
async def make_patient(api: AsyncClient, db_conn) -> AsyncIterator[Callable]:
    """Factory fixture: creates a patient via `POST /auth/register/patient`
    (AUTH_LAYER.md §6.1 — see module docstring) and guarantees Postgres +
    Mongo cleanup afterward, even on test failure. Returns a `TestPatient`
    carrying a real bearer token for that patient."""
    created: list[UUID] = []

    async def _make(disease_code: str = "parkinsons", preferred_comm_mode: str = "both") -> TestPatient:
        email = f"qa-{uuid4()}@example.test"
        resp = await api.post(
            "/auth/register/patient",
            json={
                "email": email,
                "password": "qa-test-password-not-real",
                "disease_code": disease_code,
                "preferred_comm_mode": preferred_comm_mode,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        patient_id = UUID(body["patient_id"])
        created.append(patient_id)
        return TestPatient(id=patient_id, headers={"Authorization": f"Bearer {body['access_token']}"})

    yield _make

    for patient_id in created:
        _delete_patient_rows(db_conn, patient_id)
        try:
            await delete_patient_conversations(patient_id)
        except RuntimeError as exc:
            # Best-effort cleanup only, deliberately swallowed: reproduced an
            # intermittent "attached to a different loop" error here
            # specifically (never during the test body itself, only at this
            # teardown call) when a test used Motor's insert_one earlier in
            # the same test function -- a pytest-asyncio/Motor event-loop
            # interaction in the test harness (see `event_loop` and
            # `_fresh_mongo_client_for_tests` above for the primary fix),
            # not a product bug. Leaves a synthetic, non-PHI Mongo document
            # behind in local dev Mongo on the rare occasion this fires --
            # acceptable; failing the whole test run over cleanup, after the
            # test's own assertions already passed, would not be.
            print(f"[conftest] WARNING: Mongo cleanup failed for patient {patient_id}: {exc!r}")
