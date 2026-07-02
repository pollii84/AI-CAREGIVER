from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.pipeline import run_care_agent_turn
from app.db.base import get_db
from app.mongo.conversations import start_conversation

router = APIRouter(prefix="/patients/{patient_id}/agent", tags=["care-agent"])


class StartConversationOut(BaseModel):
    conversation_id: str


class MessageIn(BaseModel):
    message: str


class MessageOut(BaseModel):
    answer: str
    citations: list[dict]
    disclaimer: str
    escalate: bool


@router.post("/conversations", response_model=StartConversationOut, status_code=201)
async def start(patient_id: UUID):
    conversation_id = await start_conversation(patient_id)
    return {"conversation_id": conversation_id}


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
async def send_message(
    patient_id: UUID,
    conversation_id: str,
    payload: MessageIn,
    db: Session = Depends(get_db),
):
    result = await run_care_agent_turn(
        db=db,
        patient_id=patient_id,
        conversation_id=conversation_id,
        user_message=payload.message,
    )
    return result
