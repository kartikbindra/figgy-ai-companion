from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Conversation, Message, Memory


class MemoryStore:
    """Handles CRUD operations for conversations, messages, and memories in SQLite."""

    @staticmethod
    async def get_or_create_conversation(
        session: AsyncSession,
        conversation_id: str,
        device_id: str = "figgy-001"
    ) -> Conversation:
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await session.execute(stmt)
        conv = result.scalar_one_or_none()
        if not conv:
            conv = Conversation(id=conversation_id, device_id=device_id)
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
        return conv

    @staticmethod
    async def add_message(
        session: AsyncSession,
        conversation_id: str,
        role: str,
        content: str,
        persona: Optional[str] = None,
        tokens: int = 0
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            persona=persona,
            tokens=tokens,
            created_at=datetime.now(timezone.utc)
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg

    @staticmethod
    async def get_recent_messages(
        session: AsyncSession,
        conversation_id: str,
        limit: int = 10
    ) -> List[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.id))
            .limit(limit)
        )
        result = await session.execute(stmt)
        # Reverse to return in chronological order
        return list(reversed(result.scalars().all()))

    @staticmethod
    async def get_conversation_message_count(
        session: AsyncSession,
        conversation_id: str
    ) -> int:
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        result = await session.execute(stmt)
        return len(result.scalars().all())

    @staticmethod
    async def store_memory(
        session: AsyncSession,
        category: str,
        key: str,
        content: str,
        confidence: float = 1.0
    ) -> Memory:
        # Check if identical key already exists in category
        stmt = select(Memory).where(Memory.category == category, Memory.key == key)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.content = content
            existing.confidence = confidence
            existing.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(existing)
            return existing

        mem = Memory(
            category=category,
            key=key,
            content=content,
            confidence=confidence,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        session.add(mem)
        await session.commit()
        await session.refresh(mem)
        return mem

    @staticmethod
    async def list_memories(
        session: AsyncSession,
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[Memory]:
        stmt = select(Memory)
        if category:
            stmt = stmt.where(Memory.category == category)
        stmt = stmt.order_by(desc(Memory.updated_at)).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def delete_memory(session: AsyncSession, memory_id: int) -> bool:
        stmt = delete(Memory).where(Memory.id == memory_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0
