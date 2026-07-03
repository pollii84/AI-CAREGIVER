"""Citation-integrity test — Testing doc §2.3.

"Separate from adversarial prompting: a structural test that inspects
agent_conversations.messages[].citations against messages[].tool_calls for
a sample of real (non-adversarial) conversations -- every citation must
resolve to a tool call made in that same turn. This catches a validator
regression that adversarial prompting might not surface (e.g., a citation
surviving from a stale/cached tool result)."

Queries the REAL Mongo agent_conversations collection (docker-compose) for
whatever conversations exist after this test run. Non-emergency turns need a
live model call to exist at all (only the emergency-bypass path writes a
conversation without ANTHROPIC_API_KEY) — see the skip reason below for the
non-vacuous case.
"""

from __future__ import annotations

import pytest

from app.mongo.client import mongo_db
from tests.conftest import HAS_ANTHROPIC_KEY


def _citations_resolve_to_tool_calls(message: dict) -> tuple[bool, str]:
    citations = message.get("citations") or []
    if not citations:
        return True, "no citations in this message -- vacuously fine"

    tool_call_source_ids = set()
    for call in message.get("tool_calls") or []:
        result = call.get("result") or {}
        for item in result.get("results") or []:
            source_id = item.get("source_id")
            if source_id:
                tool_call_source_ids.add(str(source_id))

    for citation in citations:
        cid = str(citation.get("source_id"))
        if cid not in tool_call_source_ids:
            return False, f"citation source_id {cid!r} does not resolve to any tool_call result in the same turn"
    return True, f"all {len(citations)} citation(s) resolve to a tool_call result in the same turn"


async def test_citations_resolve_to_same_turn_tool_calls():
    conversations = await mongo_db["agent_conversations"].find({}).to_list(length=200)

    if not conversations:
        pytest.skip("no agent_conversations documents exist yet in this environment's Mongo -- run the "
                    "integration/adversarial suites first (test_emergency_path.py writes at least one, "
                    "with empty citations -- vacuously fine but not real coverage of this check).")

    agent_messages = [
        m
        for convo in conversations
        for m in convo.get("messages", [])
        if m.get("role") == "agent"
    ]
    if not agent_messages:
        pytest.skip("agent_conversations documents exist but none have an 'agent'-role message yet.")

    non_vacuous_checked = 0
    failures: list[str] = []
    for message in agent_messages:
        ok, reason = _citations_resolve_to_tool_calls(message)
        if message.get("citations"):
            non_vacuous_checked += 1
        if not ok:
            failures.append(reason)

    assert not failures, f"citation-integrity violations found: {failures}"

    if non_vacuous_checked == 0:
        pytest.skip(
            f"checked {len(agent_messages)} agent message(s), all vacuously passed (zero citations in every "
            "one) -- meaningful (non-vacuous) coverage of this check requires at least one real, non-emergency "
            "conversation with actual citations, which needs ANTHROPIC_API_KEY. "
            f"HAS_ANTHROPIC_KEY={HAS_ANTHROPIC_KEY}."
        )
