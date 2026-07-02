"""agent_conversations collection — Database doc §4.1.

This is the Care Agent's audit trail: every turn's tool calls and citations
are persisted alongside the message text, not just the chat text itself.
A compliance review reads this collection to verify the output validator
(Architecture doc §4) actually enforced citation-per-claim — it's evidence,
not a convenience log.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from bson import ObjectId

from app.mongo.client import mongo_db

_COLLECTION = "agent_conversations"


async def start_conversation(patient_id: UUID) -> str:
    doc = {
        "patient_id": str(patient_id),
        "started_at": datetime.now(timezone.utc),
        "messages": [],
    }
    result = await mongo_db[_COLLECTION].insert_one(doc)
    return str(result.inserted_id)


async def append_message(
    conversation_id: str,
    role: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
    citations: list[dict[str, Any]] | None = None,
    disclaimer_shown: bool = False,
) -> None:
    message = {
        "role": role,
        "content": content,
        "tool_calls": tool_calls or [],
        "citations": citations or [],
        "disclaimer_shown": disclaimer_shown,
        "created_at": datetime.now(timezone.utc),
    }
    await mongo_db[_COLLECTION].update_one(
        {"_id": ObjectId(conversation_id)},
        {"$push": {"messages": message}},
    )


async def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    return await mongo_db[_COLLECTION].find_one({"_id": ObjectId(conversation_id)})


async def delete_patient_conversations(patient_id: UUID) -> int:
    """Deletion-request flow, Database doc §6 step (b) — hard delete, not soft."""
    result = await mongo_db[_COLLECTION].delete_many({"patient_id": str(patient_id)})
    return result.deleted_count
