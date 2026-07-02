"""Care Agent pipeline — Architecture doc §4.

    User input
       |
       v
    Intent classifier (emergency-signal -> bypass LLM, direct alert write)
       |
       v
    Claude Sonnet 5 tool-use loop (system prompt = disease_profiles.ai_behavior_contract)
       |
       v
    Structured output (answer / citations / disclaimer / escalate)
       |
       v
    Output validator (fixed disclaimer injection, disallowed-content backstop)
       |
       v
    Response + full tool-call trace persisted to Mongo (agent_conversations)

The disallowed-content check here is a best-effort backstop, NOT the
adversarial test suite (Testing doc §2.1) — that suite is the actual gate;
this is defense in depth so a single bad response doesn't ship even if the
suite has a gap.
"""

from __future__ import annotations

import json
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy.orm import Session

from app.agent.intent import is_emergency_signal
from app.agent.schema import AGENT_OUTPUT_SCHEMA
from app.agent.tools import TOOL_DEFINITIONS, TOOL_IMPLEMENTATIONS
from app.core.config import settings
from app.db.models import Alert, DiseaseProfile, Patient, SymptomEvent
from app.mongo.conversations import append_message

_MAX_TOOL_ITERATIONS = 6

_FIXED_DISCLAIMER = (
    "This is general information, not a diagnosis. Talk to your care team "
    "for guidance specific to you."
)

# Best-effort backstop only — see module docstring. Real coverage is the
# adversarial suite, Testing doc §2.1.
_DISALLOWED_PATTERNS = (
    "you have parkinson",
    "you likely have",
    "increase your dose",
    "take an extra dose",
    "stop taking your medication",
    "you don't need your medication",
)

_ESCALATION_ANSWER = (
    "I'm not able to help with that directly — this needs your care team's "
    "judgment, not mine. Please reach out to your clinician or caregiver."
)

client = AsyncAnthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else AsyncAnthropic()


async def _handle_emergency(db: Session, patient_id: UUID, conversation_id: str, user_message: str) -> dict:
    """Architecture doc §6: no LLM in the critical alert path."""
    event = SymptomEvent(
        patient_id=patient_id,
        event_type="near_fall",  # chat-detected, not sensor-confirmed — see intent.py docstring
        source="checkin_answer",
        sensor_payload={"detected_from": "care_agent_chat", "raw_text": user_message},
    )
    db.add(event)
    db.flush()
    alert = Alert(
        patient_id=patient_id,
        triggered_by="symptom_event",
        source_table="symptom_events",
        source_id=event.id,
        severity="urgent",
    )
    db.add(alert)
    db.commit()

    result = {
        "answer": "This sounds urgent — I've notified your caregiver right away. If this is a medical emergency, call emergency services now.",
        "citations": [],
        "disclaimer": _FIXED_DISCLAIMER,
        "escalate": True,
    }
    await append_message(conversation_id, role="user", content=user_message)
    await append_message(
        conversation_id,
        role="agent",
        content=result["answer"],
        tool_calls=[],
        citations=[],
        disclaimer_shown=True,
    )
    return result


def _validate_and_fix(parsed: dict) -> dict:
    """Application-layer output validator — Architecture doc §4."""
    answer_lower = parsed.get("answer", "").lower()
    if any(pattern in answer_lower for pattern in _DISALLOWED_PATTERNS):
        return {
            "answer": _ESCALATION_ANSWER,
            "citations": [],
            "disclaimer": _FIXED_DISCLAIMER,
            "escalate": True,
        }

    # Disclaimer is always the fixed boilerplate when there's any citation-backed
    # claim — never model-generated, so it can't be prompted away (Product/UX doc §4).
    if parsed.get("citations"):
        parsed["disclaimer"] = _FIXED_DISCLAIMER

    return parsed


async def run_care_agent_turn(
    db: Session,
    patient_id: UUID,
    conversation_id: str,
    user_message: str,
) -> dict:
    if is_emergency_signal(user_message):
        return await _handle_emergency(db, patient_id, conversation_id, user_message)

    patient = db.get(Patient, patient_id)
    disease_profile = db.get(DiseaseProfile, patient.disease_profile_id)

    messages: list[dict] = [{"role": "user", "content": user_message}]
    tool_call_log: list[dict] = []

    for _ in range(_MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=settings.care_agent_model,
            max_tokens=2048,
            system=disease_profile.ai_behavior_contract,
            tools=TOOL_DEFINITIONS,
            messages=messages,
            output_config={"format": {"type": "json_schema", "schema": AGENT_OUTPUT_SCHEMA}},
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                impl = TOOL_IMPLEMENTATIONS[block.name]
                result = impl(db, patient_id, block.input)
                tool_call_log.append({"tool": block.name, "input": block.input, "result": result})
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}
                )
            messages.append({"role": "user", "content": tool_results})
            continue

        # Final turn — output_config.format guarantees the text block is valid JSON
        text_block = next(b for b in response.content if b.type == "text")
        parsed = json.loads(text_block.text)
        result = _validate_and_fix(parsed)

        await append_message(conversation_id, role="user", content=user_message)
        await append_message(
            conversation_id,
            role="agent",
            content=result["answer"],
            tool_calls=tool_call_log,
            citations=result.get("citations", []),
            disclaimer_shown=bool(result.get("disclaimer")),
        )
        return result

    # Exhausted iterations without a final answer — fail safe, don't loop forever.
    fallback = {
        "answer": _ESCALATION_ANSWER,
        "citations": [],
        "disclaimer": _FIXED_DISCLAIMER,
        "escalate": True,
    }
    await append_message(conversation_id, role="user", content=user_message)
    await append_message(
        conversation_id,
        role="agent",
        content=fallback["answer"],
        tool_calls=tool_call_log,
        citations=[],
        disclaimer_shown=True,
    )
    return fallback
