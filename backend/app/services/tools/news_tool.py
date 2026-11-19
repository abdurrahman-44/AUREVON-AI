from typing import Any, Dict, Optional
from backend.app.services.live.news import NewsService


class NewsTool:
    """Retrieves verified recent news and headlines by topic or region."""

    name = "news_search"

    @classmethod
    async def execute(cls, topic: Optional[str] = "ai", max_articles: Optional[int] = 5) -> Dict[str, Any]:
        return await NewsService.get_news(
            topic=topic or "ai",
            max_articles=int(max_articles if max_articles is not None else 5),
        )
