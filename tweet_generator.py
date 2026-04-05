"""
tweet_generator.py — OpenAI GPT-4o integration for tweet generation.

Endpoint:
    POST /generate  — returns 5 tone-variant tweets for a given headline
"""

import json
import os

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

router = APIRouter(prefix="/generate", tags=["Tweet Generator"])

# Log key presence at import time so it shows up in Railway/uvicorn logs.
_api_key = os.getenv("OPENAI_API_KEY")
print(f"[tweet_generator] OpenAI key loaded: {bool(_api_key)}")

# Defer client creation to first use so a missing key surfaces as a clear
# 500 error on the /generate route rather than a silent import failure.
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Return (and lazily create) the shared OpenAI client."""
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Add it to your .env file or Railway environment variables."
            )
        _client = OpenAI(api_key=key)
    return _client

# ---------------------------------------------------------------------------
# Tone definitions fed directly into the system prompt
# ---------------------------------------------------------------------------

TONES: list[dict] = [
    {
        "name": "formal",
        "description": "diplomatic, factual, professional — no emojis",
    },
    {
        "name": "casual",
        "description": "conversational, relatable, easy language — emojis allowed",
    },
    {
        "name": "aggressive",
        "description": "hard opinions, punchy, bold statements — no emojis",
    },
    {
        "name": "analytical",
        "description": "data-driven, thread-style, insightful — no emojis",
    },
    {
        "name": "satirical",
        "description": "witty, sarcastic, humorous — emojis allowed",
    },
]


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    headline: str
    video_url: str | None = None


class TweetVariant(BaseModel):
    tone: str
    text: str


# ---------------------------------------------------------------------------
# Core generation function (reusable outside the router)
# ---------------------------------------------------------------------------

def generate_tweets(headline: str, video_url: str | None = None) -> list[dict]:
    """
    Call GPT-4o to produce 5 tone-variant tweets for *headline*.

    If *video_url* is provided it is appended to each tweet after generation,
    and the character budget is reduced accordingly so tweets stay ≤ 240 chars.
    """
    # Reserve space for " <url>" when a video URL is supplied
    url_suffix = f" {video_url}" if video_url else ""
    char_budget = 240 - len(url_suffix)

    tone_list = "\n".join(
        f'{i+1}. {t["name"].capitalize()} — {t["description"]}'
        for i, t in enumerate(TONES)
    )

    system_prompt = (
        "You are an expert social-media copywriter specialising in X (Twitter). "
        "Your output must be ONLY a valid JSON array — no markdown, no prose."
    )

    user_prompt = f"""Write exactly 5 tweets about the following headline, one per tone.

Headline: {headline}

Tones (write in this exact order):
{tone_list}

Rules:
- Each tweet must be ≤ {char_budget} characters (not counting the video URL below).
- Include 2-3 relevant SEO hashtags in every tweet.
- No emojis in formal, aggressive, or analytical tweets.
- Emojis are allowed in casual and satirical tweets.
- Do NOT include a video URL in the text — it will be appended automatically.

Return a JSON array with exactly 5 objects, each having two keys:
  "tone"  — one of: formal, casual, aggressive, analytical, satirical
  "text"  — the tweet body

Example structure (fill in real content):
[
  {{"tone": "formal",     "text": "..."}},
  {{"tone": "casual",     "text": "..."}},
  {{"tone": "aggressive", "text": "..."}},
  {{"tone": "analytical", "text": "..."}},
  {{"tone": "satirical",  "text": "..."}}
]"""

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.8,
        response_format={"type": "json_object"},  # guarantees valid JSON back
    )

    raw = response.choices[0].message.content

    # GPT-4o with response_format=json_object may wrap the array in an object.
    # Handle both {"tweets": [...]} and a bare [...].
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        # Pull the first list value regardless of key name
        variants = next(v for v in parsed.values() if isinstance(v, list))
    else:
        variants = parsed

    # Validate structure and append video URL when provided
    result = []
    for item in variants:
        text = item["text"].strip()
        if video_url:
            text = f"{text} {video_url}"
        result.append({"tone": item["tone"], "text": text})

    return result


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("", response_model=list[TweetVariant])
def generate(body: GenerateRequest):
    """Generate 5 tone-variant tweets from a headline."""
    try:
        return generate_tweets(body.headline, body.video_url)
    except Exception as exc:
        # Some OpenAI exceptions store the message in .message rather than str()
        msg = getattr(exc, "message", None) or str(exc) or type(exc).__name__
        print(f"[tweet_generator] OpenAI error: {exc!r}")
        raise HTTPException(status_code=500, detail=msg) from exc
