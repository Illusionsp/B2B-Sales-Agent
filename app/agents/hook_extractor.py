"""
Prompt 2: Hook Extractor Agent
"""
from app.llm_client import call_llm_json
from app.schemas import ResearchData, Hook

SYSTEM_PROMPT = """You are an expert B2B sales strategist who crafts compelling outreach messages.

Your Task:
Based on the company research provided, identify the THREE most powerful personalization hooks
to use in a cold email.

What Makes a Good Hook:
1. Recency: something from the last 2-3 months (funding, product launch, new hire)
2. Relevance: connected to a challenge a product/service could plausibly solve
3. Specificity: concrete and factual, not generic praise

Examples of Good Hooks:
- "Congrats on your $10M Series A led by Sequoia—exciting times!"
- "I noticed you recently hired a new VP of Sales—are you scaling your outbound efforts?"
- "Love the new AI feature you launched last month—how's the adoption been?"

Examples of Bad Hooks (avoid):
- "I love what you're doing at [Company]"
- "Your website looks great"
- "I've been following your company for a while"

Important Rules:
- Every hook MUST be backed by the research data provided — never invent a fact
- If "Information not found" appears for news/funding/hires, do not fabricate a hook about it
- If there is no major news, use an industry-specific challenge or the tech stack as a hook instead

Output ONLY a raw JSON array of exactly 3 objects:
[
  {"hook": "", "source": "", "relevance": ""}
]
"""


def run_hook_extractor(research_data: ResearchData) -> list[Hook]:
    user_prompt = f"Company Research Data:\n{research_data.model_dump_json(indent=2)}\n\nProvide the JSON array of hooks."
    result = call_llm_json(SYSTEM_PROMPT, user_prompt)

    # Model sometimes wraps the array in a dict like {"hooks": [...]}; handle both.
    if isinstance(result, dict):
        result = result.get("hooks") or next(iter(result.values()))

    return [Hook(**h) for h in result]


def select_best_hook(hooks: list[Hook], research_data: ResearchData) -> Hook:
    """
    Priority order per the original spec: funding news > product launches
    > new hires > tech stack > industry trends. We approximate this with
    simple keyword matching over the hook + source text.
    """
    priority_keywords = [
        ["funding", "raised", "series", "seed", "valuation"],
        ["launch", "released", "shipped", "feature", "product"],
        ["hire", "hired", "joins", "appointed", "new vp", "new cto", "new ceo"],
        ["stack", "aws", "shopify", "salesforce", "technology", "tech"],
    ]

    for keywords in priority_keywords:
        for hook in hooks:
            haystack = f"{hook.hook} {hook.source}".lower()
            if any(k in haystack for k in keywords):
                return hook

    # Fall back to the first hook if nothing matched a priority keyword.
    return hooks[0]
