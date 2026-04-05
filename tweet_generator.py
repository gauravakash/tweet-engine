"""
tweet_generator.py — LangChain LCEL tweet generation pipeline.

Endpoint:
    POST /generate  — returns 5 tone-variant tweets for a given headline

Architecture:
    prompt | llm | JsonOutputParser

Swapping the model requires only changing OPENAI_MODEL in the environment —
no code changes needed anywhere in this file.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from llm_config import get_llm

load_dotenv()

router = APIRouter(prefix="/generate", tags=["Tweet Generator"])

print(f"[tweet_generator] OpenAI key loaded: {bool(os.getenv('OPENAI_API_KEY'))}")


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a professional social media manager specializing in \
geopolitical and current-events content.

Generate exactly 5 tweet variants for the given headline.
Each variant must have a different tone:
1. formal     — diplomatic, factual, professional — no emojis
2. casual     — conversational, relatable, easy language — emojis allowed
3. aggressive — hard opinions, punchy, bold statements — no emojis
4. analytical — data-driven, thread-style, insightful — no emojis
5. satirical  — witty, sarcastic, humorous — emojis allowed

Rules:
- Each tweet must be ≤ {char_budget} characters (excluding any video URL).
- Include 2-3 relevant SEO hashtags in every tweet.
- No emojis in formal, aggressive, or analytical tweets.
- Do NOT include a video URL in the tweet text — it will be appended separately.
- Return ONLY valid JSON, no markdown, no explanation.

Output format:
{{
  "tweets": [
    {{"tone": "formal",     "text": "..."}},
    {{"tone": "casual",     "text": "..."}},
    {{"tone": "aggressive", "text": "..."}},
    {{"tone": "analytical", "text": "..."}},
    {{"tone": "satirical",  "text": "..."}}
  ]
}}"""

_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "Headline: {headline}\n\nGenerate the 5 tone-variant tweets now."),
])

# ---------------------------------------------------------------------------
# LCEL chain — lazily built on first call so startup doesn't fail if no key
# ---------------------------------------------------------------------------

_chain = None


def _get_chain():
    """Build (and cache) the LCEL chain: prompt | llm | parser."""
    global _chain
    if _chain is None:
        _chain = _prompt | get_llm(temperature=0.8) | JsonOutputParser()
    return _chain


# ---------------------------------------------------------------------------
# Core generation function
# ---------------------------------------------------------------------------

EXPECTED_TONES = {"formal", "casual", "aggressive", "analytical", "satirical"}


async def generate_tweets(
    headline: str,
    video_url: Optional[str] = None,
) -> list[dict]:
    """
    Invoke the LangChain chain to produce 5 tone-variant tweets.

    Args:
        headline:  The news headline or topic to tweet about.
        video_url: Optional URL appended to each tweet after generation.

    Returns:
        List of {"tone": str, "text": str} dicts, one per tone.
    """
    # Calculate char budget so the model leaves room for the appended URL
    url_suffix = f" {video_url}" if video_url else ""
    char_budget = 240 - len(url_suffix)

    try:
        result = await _get_chain().ainvoke({
            "headline": headline,
            "char_budget": char_budget,
        })
    except Exception as exc:
        print(f"[tweet_generator] LangChain error: {exc!r}")
        msg = getattr(exc, "message", None) or str(exc) or type(exc).__name__
        raise HTTPException(status_code=500, detail=f"Tweet generation failed: {msg}") from exc

    # Normalise output — handle {"tweets": [...]} and bare [...]
    if isinstance(result, list):
        tweets = result
    elif isinstance(result, dict):
        # Accept any key whose value is a list (e.g. "tweets", "variants")
        tweets = next((v for v in result.values() if isinstance(v, list)), [])
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected LLM output type: {type(result).__name__}",
        )

    # Validate all 5 tones are present
    got_tones = {t.get("tone", "").lower() for t in tweets}
    missing = EXPECTED_TONES - got_tones
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"LLM response missing tones: {', '.join(sorted(missing))}",
        )

    # Enforce hard 240-char limit and append video URL
    output = []
    for tweet in tweets:
        text = tweet.get("text", "").strip()
        # Trim to char_budget before appending the URL
        if len(text) > char_budget:
            text = text[:char_budget - 3] + "..."
        if video_url:
            text = f"{text}{url_suffix}"
        output.append({"tone": tweet["tone"].lower(), "text": text})

    return output


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    headline: str
    video_url: Optional[str] = None


class TweetVariant(BaseModel):
    tone: str
    text: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("", response_model=list[TweetVariant])
async def generate(body: GenerateRequest):
    """Generate 5 tone-variant tweets from a headline via LangChain."""
    if not body.headline.strip():
        raise HTTPException(status_code=400, detail="Headline cannot be empty")
    return await generate_tweets(body.headline, body.video_url)
