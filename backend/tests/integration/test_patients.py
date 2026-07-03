"""Integration tests — patient creation/access (Testing doc §6, onboarding).

Rewritten mid-task: the Backend Dev's auth layer (AUTH_LAYER.md) landed live
while this suite was being written. The old unauthenticated `POST /patients`
onboarding route is gone; `POST /api/v1/auth/register/patient` is the new
entry point (app/api/v1/auth.py, AUTH_LAYER.md §6.1) and `GET /patients/{id}`
now requires a bearer token (`require_patient_scope`, app/core/security.py).
These tests exercise that real, current shape — verified live, not inferred
from reading the auth code.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text


async def test_register_patient_returns_seeded_parkinsons_profile(api, make_patient):
    patient = await make_patient()

    resp = await api.get(f"/patients/{patient.id}", headers=patient.headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(patient.id)
    assert body["preferred_comm_mode"] == "both"
    # Resolves to a real UUID FK into disease_profiles (the seeded parkinsons
    # row — db/schema.sql's seed insert, per backend/README.md).
    assert uuid.UUID(body["disease_profile_id"])


async def test_register_patient_unknown_disease_code_404(api):
    resp = await api.post(
        "/auth/register/patient",
        json={
            "email": f"qa-{uuid.uuid4()}@example.test",
            "password": "qa-test-password-not-real",
            "disease_code": "nonexistent_disease",
            "preferred_comm_mode": "text",
        },
    )
    assert resp.status_code == 404


async def test_register_patient_duplicate_email_409(api, db_conn):
    email = f"qa-{uuid.uuid4()}@example.test"
    payload = {
        "email": email,
        "password": "qa-test-password-not-real",
        "disease_code": "parkinsons",
        "preferred_comm_mode": "both",
    }

    first = await api.post("/auth/register/patient", json=payload)
    assert first.status_code == 201
    patient_id = first.json()["patient_id"]

    second = await api.post("/auth/register/patient", json=payload)
    assert second.status_code == 409

    # Cleanup — bypassed make_patient's tracking to test the raw endpoint.
    db_conn.execute(text("DELETE FROM refresh_tokens WHERE actor_id = :pid"), {"pid": patient_id})
    db_conn.execute(text("DELETE FROM patient_credentials WHERE patient_id = :pid"), {"pid": patient_id})
    db_conn.execute(text("DELETE FROM patients WHERE id = :pid"), {"pid": patient_id})
    db_conn.commit()


async def test_old_unauthenticated_patients_route_is_gone(api):
    """Confirms app/api/v1/patients.py's own docstring claim: 'There is no
    internal-only remnant kept here.'"""
    resp = await api.post("/patients", json={"disease_code": "parkinsons", "preferred_comm_mode": "both"})
    assert resp.status_code == 404


async def test_get_patient_requires_auth(api):
    resp = await api.get(f"/patients/{uuid.uuid4()}")
    assert resp.status_code == 401


async def test_get_patient_rejects_a_different_patients_token(api, make_patient):
    """No caregiver-link exception applies to a bare patient-vs-patient
    request — require_patient_scope (app/core/security.py) requires
    identity.actor_id == patient_id for a patient actor."""
    owner = await make_patient()
    other = await make_patient()

    resp = await api.get(f"/patients/{owner.id}", headers=other.headers)

    assert resp.status_code == 403


async def test_get_patient_wrong_id_type_422(api, make_patient):
    # Verified live: with NO auth header, a malformed patient_id returns 401,
    # not 422 -- the auth dependency's `HTTPBearer` check runs (and fails)
    # before path-param coercion is attempted. To actually probe path
    # validation, send a valid token so the auth gate passes and the
    # malformed UUID is what's left to fail on.
    patient = await make_patient()
    resp = await api.get("/patients/not-a-uuid", headers=patient.headers)
    assert resp.status_code == 422


async def test_get_patient_wrong_id_type_without_auth_401(api):
    # Companion to the above: documents the real (auth-gate-first) ordering
    # so it isn't mistaken for a bug if noticed later.
    resp = await api.get("/patients/not-a-uuid")
    assert resp.status_code == 401
