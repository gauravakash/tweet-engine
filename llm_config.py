"""
llm_config.py — Single source of truth for LLM configuration.

To swap models, change OPENAI_MODEL in your .env or Railway dashboard.
The rest of the codebase never references a model name directly.

Supported examples:
    OPENAI_MODEL=gpt-4o          (default)
    OPENAI_MODEL=gpt-4o-mini     (cheaper / faster)
    OPENAI_MODEL=gpt-4-turbo
"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm(temperature: float = 0.8) -> ChatOpenAI:
    """
    Return a configured ChatOpenAI instance.

    All model/key settings are read from environment variables so no code
    change is needed to switch models in production.
    """
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError(
            "OPENAI_API_KEY is not set. "
            "Add it to your .env file or Railway environment variables."
        )

    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    print(f"[llm_config] Using model: {model}")

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=key,
        max_retries=3,
        request_timeout=30,
    )
