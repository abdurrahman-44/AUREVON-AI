from typing import Any, Dict, List
from backend.app.services.research.search import WebSearchService


class WebSearchTool:
    """Respects admin web_search policy and honestly reports offline/unavailable states."""

    name = "web_search"

    @classmethod
    async def execute(cls, query: str, max_results: int = 4, enabled: bool = False) -> Dict[str, Any]:
        if not enabled:
            return {
                "ok": False,
                "status": "disabled_by_policy",
                "error": "Web search is disabled in AUREVON Control Centre settings (or not requested).",
                "results": [],
            }

        clean_query = (query or "").strip()
        if not clean_query:
            return {"ok": False, "status": "invalid_input", "error": "Empty search query", "results": []}

        try:
            results: List[Dict[str, str]] = await WebSearchService.search(clean_query, max_results=max(1, min(6, max_results)))
        except Exception as exc:
            return {
                "ok": False,
                "status": "offline_or_unreachable",
                "error": f"Live web search failed or offline ({str(exc)[:120]}). Do not invent external facts.",
                "results": [],
            }

        if not results:
            return {
                "ok": False,
                "status": "no_results_or_offline",
                "error": "No live search results were returned (internet may be offline or rate-limited). State this limitation honestly.",
                "results": [],
            }

        return {
            "ok": True,
            "status": "success",
            "query": clean_query,
            "results": results,
        }
