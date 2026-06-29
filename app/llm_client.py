"""Single point of contact with the LLM provider. Every other module calls
complete() instead of talking to an SDK directly - if you ever want to swap
providers again, this is the only file that needs to change.

Currently wired to Groq (free tier, OpenAI-compatible endpoint, no EEA
billing restriction - see README for why this was chosen over Gemini/Anthropic).
"""
import re

from openai import OpenAI, RateLimitError

from app.config import settings

_client = None


class FriendlyRateLimitError(Exception):
    """Raised instead of the raw Groq/OpenAI error so the UI can show
    something actionable rather than a JSON error dump."""
    pass


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        settings.validate()
        _client = OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    return _client


def complete(system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
    """Sends one chat completion request, returns the raw text response."""
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except RateLimitError as e:
        wait_match = re.search(r"try again in ([\d.]+)([ms])", str(e))
        wait_text = ""
        if wait_match:
            amount, unit = wait_match.groups()
            unit_label = "minutes" if unit == "m" else "seconds"
            wait_text = f" Try again in about {float(amount):.0f} {unit_label}."
        raise FriendlyRateLimitError(
            "You've hit Groq's free-tier daily token limit (this resets on "
            "a rolling basis, not at midnight)." + wait_text
        ) from e
    return response.choices[0].message.content or ""


def complete_json(system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
    """Like complete(), but strips markdown code fences models sometimes
    wrap JSON in, so callers can json.loads() the result directly."""
    text = complete(system_prompt, user_prompt, max_tokens)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()
