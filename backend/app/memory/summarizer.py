import re
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from app.memory.store import MemoryStore
from app.core.logging import logger

FACT_PATTERNS = [
    (r"(?:my name is|call me)\s+([A-Za-z0-9_-]+)(?:\.|$|,)", "user_name", "User's name is {match}"),
    (r"(?:i am|i'm)\s+([A-Z][a-z0-9_-]+)(?:\.|$|,)", "user_name", "User's name is {match}"),
    (r"(?:i work as|i am a|i'm an?|i work at)\s+([A-Za-z0-9_\s]{2,35}?)(?:\.|$|,|\sand\s)", "user_profession", "User works as {match}"),
    (r"(?:i live in|i'm from|i stay in)\s+([A-Za-z0-9_\s]{2,30}?)(?:\.|$|,)", "user_location", "User lives in {match}"),
    (r"(?:i am|i'm)\s+(\d{1,2})\s*(?:years old|yo)?(?:\.|$|,)", "user_age", "User is {match} years old"),
    (r"(?:my favorite|my favourite)\s+([A-Za-z0-9_\s]{2,20}?)\s+is\s+([A-Za-z0-9_\s]{2,40}?)(?:\.|$|,)", "favorite_{match0}", "User's favorite {match0} is {match1}"),
    (r"(?:i really love|i love|i enjoy|i really like|i like)\s+([A-Za-z0-9_\s]{2,40}?)(?:\.|$|,)", "interest_{match}", "User loves {match}"),
    (r"(?:i hate|i can't stand|i despise|i don't like)\s+([A-Za-z0-9_\s]{2,40}?)(?:\.|$|,)", "dislike_{match}", "User dislikes {match}"),
    (r"(?:i'm building|i am making|i'm working on|i'm coding|i am creating)\s+([A-Za-z0-9_\s]{2,40}?)(?:\.|$|,)", "project_{match}", "User is building {match}"),
    (r"(?:i have a|my)\s+(dog|cat|pet)\s+(?:named|is)?\s*([A-Za-z0-9_-]+)", "pet_{match0}", "User has a {match0} named {match1}"),
    (r"(?:i usually|i always|i tend to)\s+([A-Za-z0-9_\s]{3,50}?)(?:\.|$|,)", "habit_{match}", "User habit: {match}"),
]


class MemoryExtractor:
    @staticmethod
    async def extract_facts_from_message(
        session: AsyncSession,
        user_message: str
    ) -> List[Dict[str, str]]:
        """Extract explicit personal facts from user input and persist to semantic memory."""
        extracted = []
        cleaned = user_message.strip()

        for pattern, key_template, content_template in FACT_PATTERNS:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 1:
                    val = groups[0].strip()
                    key = key_template.format(match=val.lower().replace(" ", "_"))
                    content = content_template.format(match=val)
                elif len(groups) == 2:
                    val0 = groups[0].strip()
                    val1 = groups[1].strip()
                    key = key_template.format(match0=val0.lower().replace(" ", "_"))
                    content = content_template.format(match0=val0, match1=val1)
                else:
                    continue

                # Store in semantic memory
                await MemoryStore.store_memory(
                    session=session,
                    category="semantic",
                    key=key,
                    content=content,
                    confidence=0.95
                )
                extracted.append({"key": key, "content": content})
                logger.info(f"Extracted semantic memory: {key} -> {content}")

        return extracted

    @staticmethod
    async def compact_conversation_if_needed(
        session: AsyncSession,
        conversation_id: str,
        threshold: int = 14,
        keep_turns: int = 8
    ) -> Optional[str]:
        """
        If a conversation grows too long, summarize older turns into an episodic memory
        to save VRAM and token budget.
        """
        count = await MemoryStore.get_conversation_message_count(session, conversation_id)
        if count <= threshold:
            return None

        recent_msgs = await MemoryStore.get_recent_messages(session, conversation_id, limit=count)
        if len(recent_msgs) <= keep_turns:
            return None

        # Take the older messages to summarize
        to_summarize = recent_msgs[:-keep_turns]
        summary_snippets = []
        for m in to_summarize:
            summary_snippets.append(f"{m.role}: {m.content[:80]}")

        summary_text = "Earlier discussion: " + " | ".join(summary_snippets[:6])
        key = f"episode_{conversation_id}_{to_summarize[0].id}"

        await MemoryStore.store_memory(
            session=session,
            category="episodic",
            key=key,
            content=summary_text,
            confidence=0.9
        )
        logger.info(f"Created episodic summary for conversation {conversation_id}: {summary_text[:100]}...")
        return summary_text
