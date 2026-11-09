import asyncio
from typing import AsyncIterator, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.llm.mock import MockLLMProvider
from app.personality.manager import personality_manager
from app.memory.store import MemoryStore
from app.memory.retrieval import MemoryRetriever
from app.memory.summarizer import MemoryExtractor
from app.core.config import settings
from app.core.logging import logger


class LLMOrchestrator:
    def __init__(self, provider: Optional[LLMProvider] = None):
        if provider:
            self.provider = provider
        elif settings.LLM_PROVIDER == "mock":
            self.provider = MockLLMProvider()
        else:
            self.provider = OllamaProvider()

    def set_provider(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def build_context(
        self,
        session: AsyncSession,
        conversation_id: str,
        user_message: str
    ) -> Tuple[str, str, str, str]:
        """
        Builds full system prompt and combined conversational context.
        Returns (system_prompt, full_prompt, persona_label, mood_label).
        """
        # 1. System prompt with personality & mood
        system_prompt, persona_label, mood_label = personality_manager.build_system_prompt(user_message)

        # 2. Retrieve persistent memories
        memory_context = await MemoryRetriever.get_memory_context(session, user_message)
        if memory_context:
            system_prompt = f"{system_prompt}\n\n{memory_context}"

        # 3. Retrieve working memory (recent turns)
        recent_messages = await MemoryStore.get_recent_messages(
            session=session,
            conversation_id=conversation_id,
            limit=settings.MAX_WORKING_MEMORY_TURNS
        )

        history_lines = []
        for msg in recent_messages:
            prefix = "User" if msg.role == "user" else "Figgy"
            history_lines.append(f"{prefix}: {msg.content}")

        history_lines.append(f"User: {user_message}\nFiggy:")
        full_prompt = "\n".join(history_lines)

        return system_prompt, full_prompt, persona_label, mood_label

    async def chat(
        self,
        session: AsyncSession,
        conversation_id: str,
        user_message: str,
        device_id: str = "figgy-001"
    ) -> Tuple[str, str, str]:
        """
        Complete chat turn.
        Returns: (reply_text, persona_label, mood_label).
        """
        await MemoryStore.get_or_create_conversation(session, conversation_id, device_id)
        system_prompt, full_prompt, persona_label, mood_label = await self.build_context(
            session, conversation_id, user_message
        )

        # Save user message
        await MemoryStore.add_message(
            session=session,
            conversation_id=conversation_id,
            role="user",
            content=user_message,
            persona=persona_label
        )

        # Call LLM
        reply = await self.provider.generate(
            prompt=full_prompt,
            system_prompt=system_prompt
        )

        # Clean reply formatting if any
        reply = reply.strip()

        # Save assistant message
        await MemoryStore.add_message(
            session=session,
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
            persona=persona_label
        )

        # Extract memories & compact in background
        if settings.AUTO_EXTRACT_MEMORY:
            asyncio.create_task(self._background_memory_tasks(conversation_id, user_message))

        return reply, persona_label, mood_label

    async def chat_stream(
        self,
        session: AsyncSession,
        conversation_id: str,
        user_message: str,
        device_id: str = "figgy-001"
    ) -> AsyncIterator[str]:
        """
        Stream chat tokens. Records full message upon completion.
        """
        await MemoryStore.get_or_create_conversation(session, conversation_id, device_id)
        system_prompt, full_prompt, persona_label, mood_label = await self.build_context(
            session, conversation_id, user_message
        )

        # Save user message
        await MemoryStore.add_message(
            session=session,
            conversation_id=conversation_id,
            role="user",
            content=user_message,
            persona=persona_label
        )

        full_reply = []
        async for token in self.provider.stream(prompt=full_prompt, system_prompt=system_prompt):
            full_reply.append(token)
            yield token

        completed_text = "".join(full_reply).strip()

        # Save assistant message
        await MemoryStore.add_message(
            session=session,
            conversation_id=conversation_id,
            role="assistant",
            content=completed_text,
            persona=persona_label
        )

        if settings.AUTO_EXTRACT_MEMORY:
            asyncio.create_task(self._background_memory_tasks(conversation_id, user_message))

    async def _background_memory_tasks(self, conversation_id: str, user_message: str):
        """Asynchronously extract facts and compact conversation without blocking response."""
        from app.database.connection import async_session
        try:
            async with async_session() as session:
                await MemoryExtractor.extract_facts_from_message(session, user_message)
                await MemoryExtractor.compact_conversation_if_needed(session, conversation_id)
        except Exception as e:
            logger.warning(f"Error in background memory extraction: {e}")


orchestrator = LLMOrchestrator()
