import csv
import io

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import validate_settings
from app.schemas import GenerateEmailRequest, GenerateEmailResponse, BatchResponse, BatchRow
from app.db import init_db, list_log, remove_from_log, RateLimitExceeded
from app.agents.orchestrator import generate_cold_email, AlreadyProcessedError

app = FastAPI(
    title="B2B Sales Agent",
    description="Multi-agent pipeline that researches a company and generates a "
    "personalized, self-reviewed cold email.",
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    problems = validate_settings()
    return {"status": "ok" if not problems else "misconfigured", "issues": problems}


@app.post("/generate-email", response_model=GenerateEmailResponse)
def generate_email(payload: GenerateEmailRequest):
    try:
        return generate_cold_email(payload.company_name, payload.company_url)
    except AlreadyProcessedError as e:
        return JSONResponse(
            status_code=409,
            content={
                "error": "This company has already been processed.",
                "existing_record": e.existing,
                "hint": f"DELETE /sent-log/{payload.company_name} to re-run intentionally.",
            },
        )
    except RateLimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    except RuntimeError as e:
        # Missing API keys, etc.
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")


@app.post("/generate-emails-batch", response_model=BatchResponse)
def generate_emails_batch(file: UploadFile = File(...)):
    """
    Accepts a CSV with columns `company_name,company_url` and runs the full
    pipeline for every row. One failed or duplicate row never aborts the batch —
    each row's outcome is reported individually, which is what a client with
    a real lead list actually needs.
    """
    raw = file.file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))

    if reader.fieldnames is None or "company_name" not in reader.fieldnames or "company_url" not in reader.fieldnames:
        raise HTTPException(
            status_code=400,
            detail="CSV must have 'company_name' and 'company_url' columns.",
        )

    results: list[BatchRow] = []
    for row in reader:
        company_name = (row.get("company_name") or "").strip()
        company_url = (row.get("company_url") or "").strip()
        if not company_name or not company_url:
            results.append(BatchRow(
                company_name=company_name or "(missing)",
                company_url=company_url or "(missing)",
                status="failed",
                error="Missing company_name or company_url",
            ))
            continue

        try:
            result = generate_cold_email(company_name, company_url)
            results.append(BatchRow(
                company_name=company_name,
                company_url=company_url,
                status="success",
                subject_line=result.subject_line,
                email_body=result.email_body,
                review_status=result.review_status,
                processing_time_seconds=result.processing_time_seconds,
            ))
        except AlreadyProcessedError as e:
            results.append(BatchRow(
                company_name=company_name,
                company_url=company_url,
                status="skipped_duplicate",
                subject_line=e.existing.get("subject_line"),
            ))
        except RateLimitExceeded as e:
            results.append(BatchRow(
                company_name=company_name,
                company_url=company_url,
                status="rate_limited",
                error=str(e),
            ))
        except Exception as e:
            results.append(BatchRow(
                company_name=company_name,
                company_url=company_url,
                status="failed",
                error=str(e),
            ))

    return BatchResponse(
        total_companies=len(results),
        succeeded=sum(1 for r in results if r.status == "success"),
        skipped_duplicates=sum(1 for r in results if r.status == "skipped_duplicate"),
        failed=sum(1 for r in results if r.status in ("failed", "rate_limited")),
        results=results,
    )


@app.get("/sent-log")
def get_sent_log():
    return {"companies": list_log()}


@app.delete("/sent-log/{company_name}")
def delete_from_log(company_name: str):
    removed = remove_from_log(company_name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{company_name} not found in log")
    return {"removed": company_name}
