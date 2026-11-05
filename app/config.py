"""
Central configuration. Loads from .env so the app never hardcodes secrets.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    MAX_REVIEW_ATTEMPTS: int = int(os.getenv("MAX_REVIEW_ATTEMPTS", "3"))
    SENT_LOG_DB_PATH: str = os.getenv("SENT_LOG_DB_PATH", "sent_log.db")


settings = Settings()


def validate_settings() -> list[str]:
    """Returns a list of human-readable problems with the current config, empty if fine."""
    problems = []
    if not settings.GROQ_API_KEY:
        problems.append("GROQ_API_KEY is not set — get one free at https://console.groq.com/keys")
    if not settings.TAVILY_API_KEY:
        problems.append("TAVILY_API_KEY is not set — get one free at https://app.tavily.com")
    return problems
