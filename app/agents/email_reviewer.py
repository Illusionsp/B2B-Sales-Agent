"""
Prompt 4: Email Reviewer/Refiner Agent
"""
from app.llm_client import call_llm_json
from app.schemas import ResearchData, DraftEmail, ReviewResult

SYSTEM_PROMPT = """You are a strict sales email critic who ensures every email meets the highest
standards for reply rates.

Your Task:
Review the drafted email against these pass/fail criteria. If it fails ANY criterion, rewrite
it immediately using the original research data to make it stronger.

Evaluation Criteria:
1. Personalization Check: FAIL if it contains no specific fact about the target company (name alone doesn't count)
2. Brevity Check: FAIL if the email is over 80 words or contains filler
3. "You/Your" Ratio: FAIL if "you"/"your" isn't used at least 3x more than "I"/"we"/"our"
4. Value Clarity: FAIL if the benefit to the recipient is vague ("help you grow", "increase efficiency")
5. CTA Specificity: FAIL if the CTA is vague ("let me know if interested") or high-friction ("schedule a demo now")

If it fails any criterion, rewrite it immediately, fixing every failure point, using the
original research. If it passes all five, return it unchanged with review_result "PASS".

Output ONLY a raw JSON object:
{
  "review_result": "PASS" or "FAIL",
  "feedback": ["specific issue 1", "specific issue 2"],
  "final_email": {"subject_line": "", "email_body": ""}
}

If PASS, feedback should be an empty array.
"""


def run_email_reviewer(research_data: ResearchData, draft_email: DraftEmail) -> ReviewResult:
    user_prompt = (
        f"Original Research Data:\n{research_data.model_dump_json(indent=2)}\n\n"
        f"Drafted Email:\n{draft_email.model_dump_json(indent=2)}\n\n"
        "Provide the review result and final email in JSON format."
    )
    result = call_llm_json(SYSTEM_PROMPT, user_prompt)
    return ReviewResult(**result)
