from fastapi import APIRouter, Depends
from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limit_dependency
from backend.app.schemas.research import ResearchRequest, ResearchResponse, SourceCitation
from backend.app.services.research.search import WebSearchService

router = APIRouter(prefix="/research", tags=["Research"])


@router.post(
    "",
    response_model=ResearchResponse,
    dependencies=[Depends(rate_limit_dependency("research", lambda: settings.RATE_LIMIT_CHAT_PER_MINUTE))],
)
async def perform_research(payload: ResearchRequest):
    results = await WebSearchService.search(payload.query, max_results=payload.max_sources)

    citations = [
        SourceCitation(
            title=r["title"],
            snippet=r["snippet"],
            url=r["url"],
        )
        for r in results
    ]

    if not citations:
        summary = (
            f"### Research Notice: {payload.query}\n"
            "No live external search results were returned (network offline, blocked, or zero matches). "
            "No fabricated sources were generated."
        )
    else:
        summary_lines = [
            f"### Research Synthesis: {payload.query}",
            f"Retrieved {len(citations)} live external references.",
            "",
        ]
        for c in citations:
            summary_lines.append(f"- **{c.title}**: {c.snippet} ([Reference]({c.url}))")
        summary = "\n".join(summary_lines)

    return ResearchResponse(
        query=payload.query,
        summary=summary,
        citations=citations,
        source_count=len(citations),
    )
