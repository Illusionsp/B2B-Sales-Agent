"""
Runs the pipeline end-to-end against the Webflow example from the original
prompt pack, printing the result. Requires GROQ_API_KEY and TAVILY_API_KEY
to be set in .env.

Usage:
    python tests/test_example.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import validate_settings
from app.db import init_db
from app.agents.orchestrator import generate_cold_email, AlreadyProcessedError


def main():
    problems = validate_settings()
    if problems:
        print("Missing configuration:")
        for p in problems:
            print(f"  - {p}")
        print("\nCopy .env.example to .env and fill in your keys first.")
        return

    init_db()

    try:
        result = generate_cold_email("Webflow", "https://webflow.com")
    except AlreadyProcessedError as e:
        print("Already processed. Existing record:")
        print(json.dumps(e.existing, indent=2))
        return

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
