"""
Live web search for the Research Agent, using Tavily's free-tier API.

This is the piece the original prompt pack skipped: it assumed
`{search_results}` would already be populated. An LLM can't browse
Crunchbase/LinkedIn on its own, so we fetch real results here first.
"""
from tavily import TavilyClient

from app.config import settings

_client: TavilyClient | None = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        if not settings.TAVILY_API_KEY:
            raise RuntimeError(
                "TAVILY_API_KEY is not set. Add it to your .env file. "
                "Get a free key at https://app.tavily.com"
            )
        _client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _client


def search_company(company_name: str, company_url: str) -> tuple[str, list[str]]:
    """
    Runs a handful of targeted queries covering the categories the Research
    Agent needs (funding, hires, tech stack, leadership), and returns:
      - a single text blob of combined result snippets (for the LLM prompt)
      - the list of source URLs actually used (for traceability/citations)
    """
    client = _get_client()
    queries = [
        f"{company_name} company overview funding employees",
        f"{company_name} recent news funding round 2026",
        f"{company_name} tech stack engineering blog",
        f"{company_name} CEO CTO VP executives leadership team",
    ]

    combined_text_parts = []
    sources = []
    seen_urls = set()

    for query in queries:
        try:
            result = client.search(
                query=query,
                search_depth="basic",
                max_results=4,
                include_domains=None,
            )
        except Exception as e:
            combined_text_parts.append(f"[Search failed for query '{query}': {e}]")
            continue

        for item in result.get("results", []):
            url = item.get("url", "")
            content = item.get("content", "")
            title = item.get("title", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append(url)
            combined_text_parts.append(f"SOURCE: {title} ({url})\n{content}\n")

    combined_text = "\n---\n".join(combined_text_parts) if combined_text_parts else (
        f"No search results found. Only known info: company URL is {company_url}."
    )
    return combined_text, sources
