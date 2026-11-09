from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.memory.store import MemoryStore
from app.core.security import verify_api_key

router = APIRouter(prefix="/memory", tags=["Memory"])


class MemoryCreateRequest(BaseModel):
    category: str = Field(..., description="Category: semantic, episodic, behavioural")
    key: str = Field(..., description="Unique key or identifier")
    content: str = Field(..., description="Memory content/fact")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MemoryResponse(BaseModel):
    id: int
    category: str
    key: str
    content: str
    confidence: float
    created_at: str
    updated_at: str


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_memories(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db)
):
    """Inspect stored memories (semantic facts, episodic summaries, behavioural patterns)."""
    memories = await MemoryStore.list_memories(session, category=category, limit=limit)
    return [
        {
            "id": m.id,
            "category": m.category,
            "key": m.key,
            "content": m.content,
            "confidence": m.confidence,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None
        }
        for m in memories
    ]


@router.post("", dependencies=[Depends(verify_api_key)])
async def create_memory(
    req: MemoryCreateRequest,
    session: AsyncSession = Depends(get_db)
):
    """Manually add or update a memory item."""
    mem = await MemoryStore.store_memory(
        session=session,
        category=req.category,
        key=req.key,
        content=req.content,
        confidence=req.confidence
    )
    return {
        "status": "stored",
        "id": mem.id,
        "key": mem.key,
        "content": mem.content
    }


@router.delete("/{memory_id}", dependencies=[Depends(verify_api_key)])
async def delete_memory(
    memory_id: int,
    session: AsyncSession = Depends(get_db)
):
    """Delete a memory item by ID."""
    success = await MemoryStore.delete_memory(session, memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted", "id": memory_id}
