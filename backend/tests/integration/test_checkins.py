"""Integration tests — check-in submission, both types (Testing doc §6,
Product/UX doc §3.1a structured / §5 mood_row).

Rewritten mid-task: app/api/v1/checkins.py picked up
`require_patient_scope` / `require_patient_write_scope` (AUTH_LAYER.md) while
this suite was being built. Every call sends the owning patient's bearer
token via `patient.headers`.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError


async def test_submit_structured_checkin(api, make_patient):
    patient = await make_patient()

    resp = await api.post(
        f"/patients/{patient.id}/checkins",
        json={
            "checkin_type": "structured",
            "answers": {
                "medication_on_time": "Yes",
                "falls": "No",
                "movement_today": 3,
            },
            "computed_score": 42.0,
            "input_mode": "text",
        },
        headers=patient.headers,
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["checkin_type"] == "structured"
    assert body["answers"]["medication_on_time"] == "Yes"
    assert body["computed_score"] == 42.0
    assert body["input_mode"] == "text"
    assert "recorded_at" in body


async def test_submit_mood_row_checkin(api, make_patient):
    patient = await make_patient()

    resp = await api.post(
        f"/patients/{patient.id}/checkins",
        json={
            "checkin_type": "mood_row",
            "answers": {"mood": "okay", "emoji": "🙂"},
            "input_mode": "voice",
        },
        headers=patient.headers,
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["checkin_type"] == "mood_row"
    assert body["answers"]["mood"] == "okay"
    assert body["computed_score"] is None
    assert body["input_mode"] == "voice"


async def test_submit_checkin_requires_auth(api, make_patient):
    patient = await make_patient()

    resp = await api.post(
        f"/patients/{patient.id}/checkins",
        json={"checkin_type": "mood_row", "answers": {"mood": "fine"}, "input_mode": "text"},
    )

    assert resp.status_code == 401


async def test_submit_checkin_rejects_a_different_patients_token(api, make_patient):
    owner = await make_patient()
    other = await make_patient()

    resp = await api.post(
        f"/patients/{owner.id}/checkins",
        json={"checkin_type": "mood_row", "answers": {"mood": "fine"}, "input_mode": "text"},
        headers=other.headers,
    )

    assert resp.status_code == 403


async def test_list_checkins_ordered_most_recent_first(api, make_patient):
    patient = await make_patient()

    first = await api.post(
        f"/patients/{patient.id}/checkins",
        json={"checkin_type": "mood_row", "answers": {"mood": "low"}, "input_mode": "text"},
        headers=patient.headers,
    )
    second = await api.post(
        f"/patients/{patient.id}/checkins",
        json={"checkin_type": "mood_row", "answers": {"mood": "better"}, "input_mode": "text"},
        headers=patient.headers,
    )

    resp = await api.get(f"/patients/{patient.id}/checkins", headers=patient.headers)

    assert resp.status_code == 200
    ids_in_order = [c["id"] for c in resp.json()]
    assert ids_in_order.index(second.json()["id"]) < ids_in_order.index(first.json()["id"])


async def test_checkin_invalid_type_rejected_by_db_constraint(api, make_patient):
    """checkins.checkin_type has a DB CHECK constraint ('structured'|
    'mood_row') but CheckinCreate (app/api/v1/checkins.py) types
    checkin_type as a bare `str` — no app-layer (422) validation. Verified
    live: this does NOT come back as an HTTP 500 response — Starlette's
    ServerErrorMiddleware sends the 500 to the client but also re-raises the
    original exception (by design, so test clients see it), so it surfaces
    here as a raised sqlalchemy.exc.IntegrityError instead of a response
    object. Documenting the actual observed failure mode, not an assumed
    one, so a future fix that adds proper request validation is a visible
    test change, not a silent one."""
    patient = await make_patient()

    with pytest.raises(IntegrityError, match="checkins_checkin_type_check"):
        await api.post(
            f"/patients/{patient.id}/checkins",
            json={"checkin_type": "not_a_real_type", "answers": {}, "input_mode": "text"},
            headers=patient.headers,
        )


async def test_checkins_data_scoped_to_own_patient(api, make_patient):
    patient_a = await make_patient()
    patient_b = await make_patient()

    await api.post(
        f"/patients/{patient_a.id}/checkins",
        json={"checkin_type": "mood_row", "answers": {"mood": "fine"}, "input_mode": "text"},
        headers=patient_a.headers,
    )

    resp = await api.get(f"/patients/{patient_b.id}/checkins", headers=patient_b.headers)

    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_checkins_rejects_a_different_patients_token(api, make_patient):
    patient_a = await make_patient()
    patient_b = await make_patient()

    resp = await api.get(f"/patients/{patient_a.id}/checkins", headers=patient_b.headers)

    assert resp.status_code == 403
