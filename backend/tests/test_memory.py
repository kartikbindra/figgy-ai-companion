import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.memory.store import MemoryStore
from app.memory.summarizer import MemoryExtractor
from app.memory.retrieval import MemoryRetriever


@pytest.mark.asyncio
async def test_memory_store_crud(db_session: AsyncSession):
    # Store semantic memory
    mem = await MemoryStore.store_memory(
        session=db_session,
        category="semantic",
        key="user_name",
        content="User's name is Kartik",
        confidence=1.0
    )
    assert mem.id is not None
    assert mem.key == "user_name"

    # List memories
    all_mems = await MemoryStore.list_memories(db_session, category="semantic")
    assert len(all_mems) == 1
    assert all_mems[0].content == "User's name is Kartik"

    # Delete memory
    deleted = await MemoryStore.delete_memory(db_session, mem.id)
    assert deleted is True

    remaining = await MemoryStore.list_memories(db_session, category="semantic")
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_memory_fact_extraction(db_session: AsyncSession):
    user_input = "My favorite food is spicy ramen."
    extracted = await MemoryExtractor.extract_facts_from_message(db_session, user_input)

    assert len(extracted) == 1
    assert "favorite_food" in extracted[0]["key"]
    assert "spicy ramen" in extracted[0]["content"]

    # Retrieve context
    context = await MemoryRetriever.get_memory_context(db_session)
    assert "spicy ramen" in context
    assert "[PERSISTENT MEMORY" in context


@pytest.mark.asyncio
async def test_conversation_compaction(db_session: AsyncSession):
    conv_id = "test-compaction"
    await MemoryStore.get_or_create_conversation(db_session, conv_id)

    # Insert 16 messages
    for i in range(16):
        role = "user" if i % 2 == 0 else "assistant"
        await MemoryStore.add_message(
            db_session,
            conversation_id=conv_id,
            role=role,
            content=f"Message turn number {i}"
        )

    # Trigger compaction
    summary = await MemoryExtractor.compact_conversation_if_needed(
        session=db_session,
        conversation_id=conv_id,
        threshold=14,
        keep_turns=6
    )

    assert summary is not None
    assert "Earlier discussion:" in summary

    # Check episodic memory stored
    episodic = await MemoryStore.list_memories(db_session, category="episodic")
    assert len(episodic) == 1
