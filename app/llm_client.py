"""
Thin wrapper around Groq's chat completions API.

Centralizing this means every agent calls one function, gets back a parsed
dict, and doesn't have to duplicate error handling or JSON-fence stripping.
"""
import json
import re
from groq import Groq

from app.config import settings

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your .env file. "
                "Get a free key at https://console.groq.com/keys"
            )
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def _strip_json_fences(text: str) -> str:
    """Groq sometimes wraps JSON in ```json ... ``` even when told not to. Strip it."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return cleaned.strip()


def call_llm_json(system_prompt: str, user_prompt: str, max_retries: int = 2) -> dict:
    """
    Calls the LLM and parses its response as JSON.
    Retries with a stricter reminder if the model returns malformed JSON —
    small/free models occasionally add stray commentary despite instructions.
    """
    client = _get_client()
    last_error = None

    for attempt in range(max_retries + 1):
        effective_system = system_prompt
        if attempt > 0:
            effective_system += (
                "\n\nCRITICAL: Your previous response was not valid JSON. "
                "Return ONLY a raw JSON object or array. No markdown, no backticks, "
                "no preamble, no explanation — just the JSON."
            )

        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": effective_system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content
        cleaned = _strip_json_fences(raw)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            last_error = e
            continue

    raise ValueError(f"LLM did not return valid JSON after {max_retries + 1} attempts: {last_error}")
