"""
Demo UI for client calls / Upwork proposal videos.

Run with:  streamlit run app_ui.py

This talks directly to the orchestrator (no need to also run uvicorn),
so it's a single command for a live demo.
"""
import time
import io
import csv

import streamlit as st

from app.config import validate_settings
from app.db import init_db, has_been_processed, remove_from_log, list_log, RateLimitExceeded
from app.agents.orchestrator import generate_cold_email, AlreadyProcessedError

st.set_page_config(page_title="B2B Sales Agent", page_icon="✉️", layout="wide")
init_db()

st.title("✉️ B2B Sales Agent — Live Demo")
st.caption(
    "Give it a company name + URL. It researches the company live on the web, "
    "picks the strongest personalization angle, drafts a cold email, and "
    "self-reviews the draft against 5 quality checks before returning it."
)

problems = validate_settings()
if problems:
    st.error("Missing configuration:\n\n" + "\n".join(f"- {p}" for p in problems))
    st.stop()

tab_single, tab_batch, tab_log = st.tabs(["Single Company", "Batch (CSV)", "Sent Log"])

# ---------------------------------------------------------------- Single ---
with tab_single:
    col1, col2 = st.columns(2)
    with col1:
        company_name = st.text_input("Company name", placeholder="Webflow")
    with col2:
        company_url = st.text_input("Company URL", placeholder="https://webflow.com")

    force_rerun = False
    existing = has_been_processed(company_name) if company_name else None
    if existing:
        st.warning(f"'{company_name}' was already processed on {existing['created_at']}.")
        force_rerun = st.checkbox("Run again anyway (removes it from the dedupe log first)")

    if st.button("Generate Email", type="primary", disabled=not (company_name and company_url)):
        if existing and force_rerun:
            remove_from_log(company_name)

        with st.spinner("Researching company, drafting, and reviewing..."):
            try:
                result = generate_cold_email(company_name, company_url)
            except AlreadyProcessedError as e:
                st.error("Already processed — check the box above to re-run.")
                result = None
            except RateLimitExceeded as e:
                st.error(str(e))
                result = None
            except Exception as e:
                st.error(f"Pipeline error: {e}")
                result = None

        if result:
            st.success(f"Done in {result.processing_time_seconds}s — {result.review_status}")

            st.subheader("📧 Final Email")
            st.text_input("Subject", value=result.subject_line, disabled=True)
            st.text_area("Body", value=result.email_body, height=140, disabled=True)

            with st.expander("🎯 Hooks considered"):
                for h in result.hooks_considered:
                    marker = "✅" if h == result.selected_hook else "•"
                    st.write(f"{marker} {h}")

            with st.expander("🔍 Research data"):
                st.json(result.research_data.model_dump())

            with st.expander("📚 Sources used"):
                for s in result.sources_used:
                    st.write(f"- {s}")

            if result.review_feedback:
                with st.expander("🛠️ Review feedback (issues caught & fixed)"):
                    for f in result.review_feedback:
                        st.write(f"- {f}")

# ----------------------------------------------------------------- Batch ---
with tab_batch:
    st.write("Upload a CSV with columns `company_name` and `company_url`.")
    uploaded = st.file_uploader("CSV file", type=["csv"])

    if uploaded and st.button("Run Batch", type="primary"):
        raw = uploaded.getvalue().decode("utf-8-sig")
        reader = list(csv.DictReader(io.StringIO(raw)))

        progress = st.progress(0, text="Starting...")
        results = []
        for i, row in enumerate(reader):
            name = (row.get("company_name") or "").strip()
            url = (row.get("company_url") or "").strip()
            progress.progress((i) / max(len(reader), 1), text=f"Processing {name}...")

            if not name or not url:
                results.append({"company_name": name, "status": "failed", "error": "missing fields"})
                continue
            try:
                r = generate_cold_email(name, url)
                results.append({
                    "company_name": name,
                    "status": "success",
                    "subject_line": r.subject_line,
                    "review_status": r.review_status,
                    "time_s": r.processing_time_seconds,
                })
            except AlreadyProcessedError:
                results.append({"company_name": name, "status": "skipped_duplicate"})
            except RateLimitExceeded as e:
                results.append({"company_name": name, "status": "rate_limited", "error": str(e)})
                time.sleep(5)
            except Exception as e:
                results.append({"company_name": name, "status": "failed", "error": str(e)})

        progress.progress(1.0, text="Done")
        st.dataframe(results, use_container_width=True)

        succeeded = sum(1 for r in results if r["status"] == "success")
        st.info(f"{succeeded}/{len(results)} emails generated successfully.")

# ------------------------------------------------------------------- Log ---
with tab_log:
    log = list_log()
    if not log:
        st.write("No companies processed yet.")
    else:
        st.dataframe(log, use_container_width=True)
        remove_name = st.text_input("Remove a company from the dedupe log")
        if st.button("Remove") and remove_name:
            if remove_from_log(remove_name):
                st.success(f"Removed {remove_name}")
                st.rerun()
            else:
                st.error("Not found")
