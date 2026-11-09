import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.llm.orchestrator import orchestrator
from app.core.security import verify_api_key
from app.core.logging import logger

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User's input message")
    conversation_id: str = Field(default="conv-default", description="Conversation session ID")
    device_id: str = Field(default="figgy-001", description="Identifier of the client/hardware")


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    persona: str
    mood: str
    status: str = "completed"


@router.post("", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def chat_endpoint(
    req: ChatRequest,
    session: AsyncSession = Depends(get_db)
):
    """Standard non-streaming chat endpoint."""
    try:
        reply, persona, mood = await orchestrator.chat(
            session=session,
            conversation_id=req.conversation_id,
            user_message=req.message,
            device_id=req.device_id
        )
        return ChatResponse(
            conversation_id=req.conversation_id,
            reply=reply,
            persona=persona,
            mood=mood,
            status="completed"
        )
    except ConnectionError as ce:
        logger.error(f"Inference provider connection error: {ce}")
        raise HTTPException(status_code=503, detail=str(ce))
    except Exception as e:
        logger.error(f"Unexpected error in /chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal inference failure")


@router.post("/stream", dependencies=[Depends(verify_api_key)])
async def chat_stream_endpoint(
    req: ChatRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Server-Sent Events (SSE) streaming endpoint.
    Yields data: {"token": "..."} as each token is generated.
    """
    async def event_generator():
        try:
            async for token in orchestrator.chat_stream(
                session=session,
                conversation_id=req.conversation_id,
                user_message=req.message,
                device_id=req.device_id
            ):
                payload = json.dumps({"token": token})
                yield f"data: {payload}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except ConnectionError as ce:
            err = json.dumps({"error": str(ce)})
            yield f"data: {err}\n\n"
        except Exception as e:
            err = json.dumps({"error": f"Stream error: {str(e)}"})
            yield f"data: {err}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
