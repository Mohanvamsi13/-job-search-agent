"""Loads configuration from environment variables / .env file.

Using Groq (free tier, OpenAI-compatible API, no EEA billing restriction)
instead of the Anthropic API directly, so this runs at zero cost."""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    groq_base_url: str = "https://api.groq.com/openai/v1"

    def validate(self) -> None:
        if not self.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env "
                "and add your key from console.groq.com."
            )


settings = Settings()
