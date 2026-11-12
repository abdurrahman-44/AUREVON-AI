import re
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx


class WebSearchService:
    """Provides web search queries and citation retrieval without proprietary API requirements."""

    DUCKDUCKGO_API = "https://api.duckduckgo.com/"
    DUCKDUCKGO_HTML = "https://html.duckduckgo.com/html/"

    @classmethod
    async def search(cls, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

        # 1. Try DuckDuckGo Instant Answer API
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                res = await client.get(
                    cls.DUCKDUCKGO_API,
                    params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                )
                if res.status_code == 200:
                    data = res.json()
                    abstract = data.get("AbstractText", "")
                    abstract_url = data.get("AbstractURL", "")
                    if abstract and abstract_url:
                        results.append({
                            "title": data.get("Heading", query),
                            "snippet": abstract,
                            "url": abstract_url,
                        })
                    for topic in data.get("RelatedTopics", [])[:max_results]:
                        if isinstance(topic, dict) and "Text" in topic and "FirstURL" in topic:
                            results.append({
                                "title": topic.get("Text", "").split(" - ")[0],
                                "snippet": topic.get("Text", ""),
                                "url": topic.get("FirstURL", ""),
                            })
        except Exception:
            pass

        # 2. Try DuckDuckGo Lite HTML Search
        if len(results) < max_results:
            try:
                async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                    resp = await client.post(
                        cls.DUCKDUCKGO_HTML,
                        data={"q": query},
                    )
                    if resp.status_code == 200:
                        html = resp.text
                        # Regex match result snippets
                        matches = re.findall(
                            r'<a class="result__url" href="([^"]+)".*?<a class="result__snippet[^>]*>(.*?)</a>',
                            html,
                            re.DOTALL,
                        )
                        for url_raw, snippet_raw in matches[:max_results]:
                            cleaned_snippet = re.sub(r"<[^>]+>", "", snippet_raw).strip()
                            clean_url = urllib.parse.unquote(url_raw).strip()
                            if clean_url.startswith("//duckduckgo.com/l/?uddg="):
                                clean_url = clean_url.split("uddg=")[1].split("&")[0]
                                clean_url = urllib.parse.unquote(clean_url)
                            if clean_url.startswith("http"):
                                results.append({
                                    "title": clean_url.split("/")[2] if len(clean_url.split("/")) > 2 else query,
                                    "snippet": cleaned_snippet,
                                    "url": clean_url,
                                })
            except Exception:
                pass

        return results[:max_results]
