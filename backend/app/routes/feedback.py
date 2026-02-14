from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app import logging_db

router = APIRouter()


class FeedbackRequest(BaseModel):
    interaction_id: str
    feedback: str  # "up" | "down"
    comment: str | None = None


@router.post("/api/feedback")
def submit_feedback(body: FeedbackRequest):
    if body.feedback not in ("up", "down"):
        raise HTTPException(status_code=400, detail="feedback must be 'up' or 'down'")
    ok = logging_db.update_feedback(body.interaction_id, body.feedback, body.comment)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to record feedback")
    return {"status": "ok"}
