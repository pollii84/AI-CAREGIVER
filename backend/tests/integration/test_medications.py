"""Integration tests — medication CRUD (Testing doc §6).

Rewritten mid-task: app/api/v1/medications.py picked up
`require_patient_scope` / `require_patient_write_scope` (AUTH_LAYER.md) while
this suite was being built. Every call now sends the owning patient's bearer
token via `patient.headers` (see tests/conftest.py's auth migration note).
"""

from __future__ import annotations

from sqlalchemy import text


async def test_add_medication(api, make_patient):
    patient = await make_patient()

    resp = await api.post(
        f"/patients/{patient.id}/medications",
        json={"name": "Carbidopa-Levodopa", "dosage": "25-100mg", "schedule_rrule": "FREQ=DAILY;BYHOUR=8,14,20"},
        headers=patient.headers,
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Carbidopa-Levodopa"
    assert body["dosage"] == "25-100mg"
    assert body["schedule_rrule"] == "FREQ=DAILY;BYHOUR=8,14,20"
    assert body["active"] is True


async def test_add_medication_requires_auth(api, make_patient):
    patient = await make_patient()

    resp = await api.post(
        f"/patients/{patient.id}/medications",
        json={"name": "Carbidopa-Levodopa", "dosage": "25-100mg", "schedule_rrule": "FREQ=DAILY;BYHOUR=8"},
    )

    assert resp.status_code == 401


async def test_add_medication_rejects_a_different_patients_token(api, make_patient):
    """AUTH_LAYER.md §4.1 write-route rule, enforced via
    require_patient_write_scope: even a valid *patient* token that isn't the
    URL's patient_id must be rejected."""
    owner = await make_patient()
    other = await make_patient()

    resp = await api.post(
        f"/patients/{owner.id}/medications",
        json={"name": "Rasagiline", "dosage": "1mg", "schedule_rrule": "FREQ=DAILY;BYHOUR=8"},
        headers=other.headers,
    )

    assert resp.status_code == 403


async def test_list_medications_for_new_patient_is_empty(api, make_patient):
    patient = await make_patient()

    resp = await api.get(f"/patients/{patient.id}/medications", headers=patient.headers)

    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_medications_returns_added_medication(api, make_patient):
    patient = await make_patient()
    await api.post(
        f"/patients/{patient.id}/medications",
        json={"name": "Ropinirole", "dosage": "2mg", "schedule_rrule": "FREQ=DAILY;BYHOUR=9"},
        headers=patient.headers,
    )

    resp = await api.get(f"/patients/{patient.id}/medications", headers=patient.headers)

    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert "Ropinirole" in names


async def test_list_medications_excludes_inactive(api, make_patient, db_conn):
    patient = await make_patient()
    add_resp = await api.post(
        f"/patients/{patient.id}/medications",
        json={"name": "Amantadine", "dosage": "100mg", "schedule_rrule": "FREQ=DAILY;BYHOUR=8"},
        headers=patient.headers,
    )
    med_id = add_resp.json()["id"]

    # No PATCH/DELETE route exists yet for medications — deactivate directly
    # to test the `list_medications` filter (`Medication.active.is_(True)`,
    # app/api/v1/medications.py) in isolation.
    db_conn.execute(text("UPDATE medications SET active = false WHERE id = :id"), {"id": med_id})
    db_conn.commit()

    resp = await api.get(f"/patients/{patient.id}/medications", headers=patient.headers)

    assert resp.status_code == 200
    assert med_id not in [m["id"] for m in resp.json()]


async def test_medications_data_scoped_to_own_patient(api, make_patient):
    """Data-layer scoping: patient_b's own token, reading patient_b's own
    (empty) list, never sees patient_a's medication."""
    patient_a = await make_patient()
    patient_b = await make_patient()

    await api.post(
        f"/patients/{patient_a.id}/medications",
        json={"name": "Rasagiline", "dosage": "1mg", "schedule_rrule": "FREQ=DAILY;BYHOUR=8"},
        headers=patient_a.headers,
    )

    resp = await api.get(f"/patients/{patient_b.id}/medications", headers=patient_b.headers)

    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_medications_rejects_a_different_patients_token(api, make_patient):
    """Access-control complement to the data-scoping test above: patient_b's
    token must not even be allowed to read patient_a's list (403 before any
    query runs), not just "happens to return an empty/foreign-filtered
    result." Testing doc §3's row-level access matrix, patient-vs-patient
    cell."""
    patient_a = await make_patient()
    patient_b = await make_patient()

    resp = await api.get(f"/patients/{patient_a.id}/medications", headers=patient_b.headers)

    assert resp.status_code == 403
