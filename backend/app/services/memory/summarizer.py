from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import ConversationSummary
from backend.app.repositories.message_repo import MessageRepository


class ConversationSummarizer:
    """Maintains a rolling compact summary of older turns once conversations grow past recent window."""

    RECENT_WINDOW = 14
    MAX_SUMMARY_CHARS = 1200

    @classmethod
    async def get_or_update_summary(
        cls,
        db: AsyncSession,
        conversation_id: str,
        recent_window: int = RECENT_WINDOW,
    ) -> Optional[str]:
        msg_repo = MessageRepository(db)
        total_count = await msg_repo.get_message_count(conversation_id)
        if total_count <= recent_window:
            return None

        existing = (
            await db.execute(
                select(ConversationSummary).where(ConversationSummary.conversation_id == conversation_id)
            )
        ).scalar_one_or_none()

        older_needed = total_count - recent_window
        if existing and existing.summarized_message_count >= older_needed and existing.summary_text:
            return existing.summary_text

        all_msgs = await msg_repo.get_all_messages_for_conversation(conversation_id)
        older_msgs = all_msgs[:-recent_window] if len(all_msgs) > recent_window else []
        if not older_msgs:
            return None

        bullets = []
        for m in older_msgs[-16:]:
            snippet = " ".join((m.content or "").split())
            if not snippet:
                continue
            limit = 110 if m.role == "user" else 90
            if len(snippet) > limit:
                snippet = snippet[:limit].rstrip() + "..."
            label = "User" if m.role == "user" else "Assistant"
            bullets.append(f"- {label}: {snippet}")

        summary_text = "\n".join(bullets)
        if len(summary_text) > cls.MAX_SUMMARY_CHARS:
            summary_text = summary_text[-cls.MAX_SUMMARY_CHARS:]

        now = datetime.now(timezone.utc)
        last_id = older_msgs[-1].id
        if existing:
            existing.summary_text = summary_text
            existing.summarized_message_count = len(older_msgs)
            existing.last_message_id = last_id
            existing.updated_at = now
        else:
            existing = ConversationSummary(
                conversation_id=conversation_id,
                summary_text=summary_text,
                summarized_message_count=len(older_msgs),
                last_message_id=last_id,
                updated_at=now,
            )
            db.add(existing)
        await db.commit()
        return summary_text
