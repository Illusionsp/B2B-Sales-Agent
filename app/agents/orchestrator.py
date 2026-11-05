"""
Prompt 5: Master Orchestrator — chains all 4 agents and adds the guardrails
the original spec was missing: real search, dedupe, and rate limiting.
"""
import time

from app.config import settings
from app.schemas import GenerateEmailResponse
from app.db import has_been_processed, record_processed, check_rate_limit
from app.agents.research_agent import run_research_agent
from app.agents.hook_extractor import run_hook_extractor, select_best_hook
from app.agents.email_writer import run_email_writer
from app.agents.email_reviewer import run_email_reviewer


class AlreadyProcessedError(Exception):
    def __init__(self, existing: dict):
        self.existing = existing
        super().__init__(f"Company already processed: {existing.get('company_name')}")


def generate_cold_email(company_name: str, company_url: str) -> GenerateEmailResponse:
    start = time.monotonic()

    # Guardrail 1: rate limit (raises RateLimitExceeded if over the cap)
    check_rate_limit()

    # Guardrail 2: dedupe — don't silently re-generate/re-send for the same company
    existing = has_been_processed(company_name)
    if existing:
        raise AlreadyProcessedError(existing)

    # Step 1: research (live search + structuring)
    research_data = run_research_agent(company_name, company_url)

    # Step 2: extract hooks
    hooks = run_hook_extractor(research_data)

    # Step 3: pick best hook by priority order
    selected_hook = select_best_hook(hooks, research_data)

    # Step 4: draft email
    draft = run_email_writer(research_data, selected_hook)

    # Step 5: review loop, max MAX_REVIEW_ATTEMPTS
    attempts = 0
    review = run_email_reviewer(research_data, draft)
    attempts += 1

    while review.review_result != "PASS" and attempts < settings.MAX_REVIEW_ATTEMPTS:
        draft = review.final_email
        review = run_email_reviewer(research_data, draft)
        attempts += 1

    status = (
        f"PASSED after {attempts} attempt{'s' if attempts != 1 else ''}"
        if review.review_result == "PASS"
        else f"FAILED after {attempts} attempts — best available draft returned"
    )

    # Record in the dedupe ledger regardless of pass/fail, so a bad lead
    # doesn't get silently retried into a duplicate send.
    record_processed(company_name, company_url, review.final_email.subject_line)

    elapsed = round(time.monotonic() - start, 2)

    return GenerateEmailResponse(
        subject_line=review.final_email.subject_line,
        email_body=review.final_email.email_body,
        hooks_considered=[h.hook for h in hooks],
        selected_hook=selected_hook.hook,
        review_status=status,
        review_feedback=review.feedback,
        sources_used=research_data.sources_used,
        research_data=research_data,
        processing_time_seconds=elapsed,
    )
