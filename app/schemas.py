"""
Pydantic models — one per agent's input/output, plus the final API contract.
Keeping these explicit (rather than passing raw dicts between agents) makes
each agent's expected shape self-documenting and catches malformed LLM output early.
"""
from typing import Optional
from pydantic import BaseModel, Field


class GenerateEmailRequest(BaseModel):
    company_name: str = Field(..., min_length=1)
    company_url: str = Field(..., min_length=1)


class DecisionMaker(BaseModel):
    name: str = "Information not found"
    title: str = "Information not found"
    linkedin_url: Optional[str] = None


class ResearchData(BaseModel):
    company_name: str
    industry: str = "Information not found"
    description: str = "Information not found"
    employee_count: str = "Information not found"
    funding: str = "Information not found"
    recent_news: list[str] = []
    tech_stack: list[str] = []
    potential_pain_points: list[str] = []
    key_decision_makers: list[DecisionMaker] = []
    sources_used: list[str] = []  # URLs actually returned by search — for traceability


class Hook(BaseModel):
    hook: str
    source: str
    relevance: str


class DraftEmail(BaseModel):
    subject_line: str
    email_body: str


class ReviewResult(BaseModel):
    review_result: str  # "PASS" or "FAIL"
    feedback: list[str] = []
    final_email: DraftEmail


class GenerateEmailResponse(BaseModel):
    subject_line: str
    email_body: str
    hooks_considered: list[str]
    selected_hook: str
    review_status: str
    review_feedback: list[str]
    sources_used: list[str]
    research_data: ResearchData
    processing_time_seconds: float = 0.0


class BatchRow(BaseModel):
    company_name: str
    company_url: str
    status: str  # "success", "skipped_duplicate", "failed", "rate_limited"
    subject_line: Optional[str] = None
    email_body: Optional[str] = None
    review_status: Optional[str] = None
    error: Optional[str] = None
    processing_time_seconds: float = 0.0


class BatchResponse(BaseModel):
    total_companies: int
    succeeded: int
    skipped_duplicates: int
    failed: int
    results: list[BatchRow]
