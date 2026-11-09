from fastapi import APIRouter
from backend.app.schemas.research import ResearchRequest, ResearchResponse, SourceCitation
from backend.app.services.research.search import WebSearchService

router = APIRouter(prefix="/research", tags=["Research"])


@router.post("", response_model=ResearchResponse)
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

    # Generate synthesized executive summary of the findings
    summary_lines = [
        f"### Research Synthesis: {payload.query}",
        f"Aggregated {len(citations)} external references and factual sources.",
        "",
    ]
    for c in citations:
        summary_lines.append(f"- **{c.title}**: {c.snippet} ([Reference]({c.url}))")

    return ResearchResponse(
        query=payload.query,
        summary="\n".join(summary_lines),
        citations=citations,
        source_count=len(citations),
    )
