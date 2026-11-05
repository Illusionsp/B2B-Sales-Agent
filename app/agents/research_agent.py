"""
Prompt 1: Web Research Agent — now backed by real search results instead of
an assumed {search_results} variable.
"""
from app.llm_client import call_llm_json
from app.search_client import search_company
from app.schemas import ResearchData

SYSTEM_PROMPT = """You are a senior business intelligence analyst specializing in B2B company research.

Your Task:
Given a company name, URL, and real web search results, extract the following structured data:

1. Company Overview: full name, description, industry/niche, employee count, funding stage
2. Recent News (last 3-6 months): funding rounds, product launches, key hires, partnerships/acquisitions
3. Tech Stack: technologies used, recent migrations
4. Pain Points/Challenges: likely problems based on industry, role, or recent news
5. Key Decision Makers: names, titles, LinkedIn profiles if present in the search results

Important Rules:
- Only use information that actually appears in the provided search results
- If you cannot find definitive information for a field, use exactly "Information not found"
- Do not invent names, numbers, or events that are not in the search results
- Be specific and factual — no speculation presented as fact

Output ONLY a raw JSON object with exactly these keys:
{
  "company_name": "",
  "industry": "",
  "description": "",
  "employee_count": "",
  "funding": "",
  "recent_news": [],
  "tech_stack": [],
  "potential_pain_points": [],
  "key_decision_makers": [{"name": "", "title": "", "linkedin_url": null}]
}
"""


def run_research_agent(company_name: str, company_url: str) -> ResearchData:
    search_text, sources = search_company(company_name, company_url)

    user_prompt = (
        f"Company Name: {company_name}\n"
        f"Company URL: {company_url}\n\n"
        f"Search Results:\n{search_text}\n\n"
        "Provide the structured JSON output described in your instructions."
    )

    result = call_llm_json(SYSTEM_PROMPT, user_prompt)
    result["company_name"] = result.get("company_name") or company_name
    result["sources_used"] = sources

    return ResearchData(**result)
