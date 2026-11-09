from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.memory.store import MemoryStore


class MemoryRetriever:
    @staticmethod
    async def get_memory_context(
        session: AsyncSession,
        user_message: str = "",
        max_items: int = 5
    ) -> str:
        """
        Retrieve relevant semantic and episodic memories to inject into Figgy's context.
        Prioritizes semantic user preferences and recent episodic milestones.
        """
        # Fetch up to max_items semantic memories
        semantic_memories = await MemoryStore.list_memories(session, category="semantic", limit=max_items)
        # Fetch recent episodic memories
        episodic_memories = await MemoryStore.list_memories(session, category="episodic", limit=2)

        all_memories = semantic_memories + episodic_memories
        if not all_memories:
            return ""

        lines = ["[PERSISTENT MEMORY & USER CONTEXT]"]
        for mem in all_memories:
            lines.append(f"- ({mem.category}) {mem.content}")
        lines.append("[Use this memory naturally when relevant. Do not quote it mechanically.]\n")

        return "\n".join(lines)
