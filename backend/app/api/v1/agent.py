from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.pipeline import run_care_agent_turn
from app.core.security import require_patient_self
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
async def start(verified_patient_id: UUID = Depends(require_patient_self)):
    conversation_id = await start_conversation(verified_patient_id)
    return {"conversation_id": conversation_id}


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
async def send_message(
    conversation_id: str,
    payload: MessageIn,
    db: Session = Depends(get_db),
    verified_patient_id: UUID = Depends(require_patient_self),
):
    # AUTH_LAYER.md §5.1-§5.3: require_patient_self is stricter than the
    # generic require_patient_scope — a caregiver link is never sufficient
    # here, however active, because Care Agent conversations are
    # patient-private (Database doc §8). The dependency's return value is
    # what's threaded into the pipeline, not the raw path param, so it can't
    # silently diverge from what was authorized (§5.2).
    result = await run_care_agent_turn(
        db=db,
        patient_id=verified_patient_id,
        conversation_id=conversation_id,
        user_message=payload.message,
    )
    return result
