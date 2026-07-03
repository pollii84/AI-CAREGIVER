"""Emergency/Alert path integration test — Testing doc §4 + the
"emergency-adjacent, misdirected to chat" row of §2.1's adversarial table.

Verifies, against the real docker-compose Postgres/Timescale + Mongo stack
(no mocked DB — only the Anthropic client is monkeypatched, and only to
*prove* it's unreachable):

  1. A chat message containing a recognized emergency keyword never reaches
     the Claude API — app/agent/pipeline.py's `is_emergency_signal` bypass,
     Architecture doc §6: "no LLM in the critical alert path — latency and
     reliability requirements exclude it." This is Testing doc §4's
     "No-LLM-in-path verification," done as a real assertion (patch-and-fail-
     if-called), not just "the response looked right so it probably didn't
     call the model."
  2. Real rows land in `symptom_events` and `alerts` (not just a 200 OK).
  3. The Mongo `agent_conversations` transcript records the exchange.

This automates the manual pass already done once for this stack (git log
7ca21e9: "full API smoke test (create patient -> add medication -> submit
check-in -> emergency-bypass chat path) against real Postgres + Mongo").

Runs unconditionally, with or without ANTHROPIC_API_KEY — that's the entire
point of the architecture being tested (Testing doc §4's deterministic,
no-LLM alert path is priority 3, above accessibility and below only AI
adversarial safety + compliance).

Rewritten mid-task: app/api/v1/agent.py picked up `require_patient_self`
(AUTH_LAYER.md §5.1-§5.3, stricter than the generic patient-scope check —
no caregiver-link exception at all, ever, for Care Agent routes) while this
suite was being built. Calls send the patient's own bearer token.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.mongo.conversations import get_conversation


class _ReachedLLMCallSite(Exception):
    """Raised by the monkeypatched Anthropic client to prove control flow
    got as far as the network call — used by the negative control below."""


async def test_fall_signal_bypasses_llm_and_writes_alert_rows(api, make_patient, db_conn, monkeypatch):
    patient = await make_patient()

    import app.agent.pipeline as pipeline_module

    def _fail_if_called(*args, **kwargs):
        raise AssertionError(
            "Claude API was called for an emergency-signal message. "
            "Architecture doc §6 requires the fall/emergency path to never "
            "call the LLM (Testing doc §4's no-LLM-in-path check)."
        )

    monkeypatch.setattr(pipeline_module.client.messages, "create", _fail_if_called)

    start = await api.post(f"/patients/{patient.id}/agent/conversations", headers=patient.headers)
    assert start.status_code == 201
    conversation_id = start.json()["conversation_id"]

    before = datetime.now(timezone.utc)
    resp = await api.post(
        f"/patients/{patient.id}/agent/conversations/{conversation_id}/messages",
        json={"message": "I just fell and I'm dizzy"},
        headers=patient.headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["escalate"] is True
    assert body["citations"] == []
    assert "caregiver" in body["answer"].lower()

    # --- Postgres: real rows, queried back over a fresh connection ---
    event_row = db_conn.execute(
        text(
            "SELECT id, event_type, source, sensor_payload, recorded_at FROM symptom_events "
            "WHERE patient_id = :pid ORDER BY recorded_at DESC LIMIT 1"
        ),
        {"pid": str(patient.id)},
    ).mappings().first()
    assert event_row is not None, "no symptom_events row written for the fall signal"
    assert event_row["event_type"] == "near_fall"
    assert event_row["source"] == "checkin_answer"
    assert event_row["sensor_payload"]["detected_from"] == "care_agent_chat"
    assert event_row["sensor_payload"]["raw_text"] == "I just fell and I'm dizzy"
    assert event_row["recorded_at"] >= before

    alert_row = db_conn.execute(
        text(
            "SELECT patient_id, triggered_by, source_table, source_id, severity, recorded_at FROM alerts "
            "WHERE patient_id = :pid ORDER BY recorded_at DESC LIMIT 1"
        ),
        {"pid": str(patient.id)},
    ).mappings().first()
    assert alert_row is not None, "no alerts row written for the fall signal"
    assert alert_row["triggered_by"] == "symptom_event"
    assert alert_row["source_table"] == "symptom_events"
    assert str(alert_row["source_id"]) == str(event_row["id"])
    assert alert_row["severity"] == "urgent"
    assert alert_row["recorded_at"] >= before

    # --- Mongo: real conversation transcript ---
    convo = await get_conversation(conversation_id)
    assert convo is not None
    assert len(convo["messages"]) == 2
    assert convo["messages"][0]["role"] == "user"
    assert convo["messages"][0]["content"] == "I just fell and I'm dizzy"
    assert convo["messages"][1]["role"] == "agent"
    assert convo["messages"][1]["disclaimer_shown"] is True
    assert convo["messages"][1]["tool_calls"] == []
    assert convo["messages"][1]["citations"] == []


async def test_non_emergency_message_reaches_llm_call_site(api, make_patient, monkeypatch):
    """Negative control for the test above. Without this, a bug that made
    the emergency bypass swallow ALL messages (not just emergency ones)
    would still pass the positive test — this proves the "no LLM call"
    assertion is actually exercising is_emergency_signal's branch logic, not
    a bypass that fires unconditionally. Doesn't need ANTHROPIC_API_KEY: it
    only proves the code *tried* to reach the network, via a sentinel
    exception, never an actual request."""
    patient = await make_patient()

    import app.agent.pipeline as pipeline_module

    def _sentinel(*args, **kwargs):
        raise _ReachedLLMCallSite("control flow reached the Claude API call site, as expected")

    monkeypatch.setattr(pipeline_module.client.messages, "create", _sentinel)

    start = await api.post(f"/patients/{patient.id}/agent/conversations", headers=patient.headers)
    conversation_id = start.json()["conversation_id"]

    try:
        await api.post(
            f"/patients/{patient.id}/agent/conversations/{conversation_id}/messages",
            json={"message": "What's a good stretch routine for stiffness?"},
            headers=patient.headers,
        )
    except _ReachedLLMCallSite:
        return
    except Exception as exc:  # pragma: no cover - diagnostic aid on unexpected shape
        raise AssertionError(
            f"expected _ReachedLLMCallSite to propagate through the ASGI transport, got {exc!r} instead"
        ) from exc
    else:
        raise AssertionError(
            "non-emergency message never reached the Claude API call site -- "
            "is_emergency_signal may be over-matching, which would make the "
            "positive no-LLM-call test above a false positive"
        )


async def test_start_conversation_requires_patient_actor_token(api, make_patient):
    patient = await make_patient()

    resp = await api.post(f"/patients/{patient.id}/agent/conversations")

    assert resp.status_code == 401


async def test_start_conversation_rejects_a_different_patients_token(api, make_patient):
    """AUTH_LAYER.md §5.1: require_patient_self has NO caregiver-link
    exception, unlike require_patient_scope -- Care Agent transcripts are
    patient-private (Database doc §8) with no sharing feature in MVP. This
    test only exercises the patient-vs-patient case (a second patient's
    otherwise-valid token); the caregiver-link exception itself would need a
    seeded patient_caregiver_links row + a caregiver credential, which is
    outside this test's scope but is the same code path."""
    owner = await make_patient()
    other = await make_patient()

    resp = await api.post(f"/patients/{owner.id}/agent/conversations", headers=other.headers)

    assert resp.status_code == 403
