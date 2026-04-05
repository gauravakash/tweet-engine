"""
main.py — FastAPI entry point for Tweet Engine.

Run locally:
    uvicorn main:app --reload --port 8000

The frontend is served at / (index.html = dashboard).
All API routes are prefixed so they don't collide with static files.
"""

import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import init_db
from accounts import router as accounts_router
from news_topics import router as topics_router
from tweet_generator import router as generator_router
from scheduler import router as queue_router
from scheduler import start_scheduler, shutdown_scheduler
from poster import router as history_router


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Tweet Engine",
    description="Personal dashboard to manage X accounts and schedule AI-generated tweets.",
    version="0.1.0",
    lifespan=lifespan,
)

# ALLOWED_ORIGINS env var: comma-separated list of allowed origins.
# Default "*" works for local dev; set to your Railway domain in production.
# Example: ALLOWED_ORIGINS=https://tweet-engine.up.railway.app
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers — all registered before the static file mount ──────────────
app.include_router(accounts_router)
app.include_router(topics_router)
app.include_router(generator_router)
app.include_router(queue_router)
app.include_router(history_router)


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------

class OpenAIKeyBody(BaseModel):
    key: str


@app.get("/settings/openai-key")
def get_openai_key_status():
    """Return whether the OpenAI key is configured (masked, never the raw value)."""
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return {"set": False, "masked": None}
    masked = key[:4] + "••••" + key[-4:] if len(key) > 8 else "••••"
    return {"set": True, "masked": masked}


@app.post("/settings/openai-key", status_code=204)
def save_openai_key(body: OpenAIKeyBody):
    """
    Write the OpenAI API key to the local .env file.
    Only useful for local development — on Railway, use environment variables.
    """
    key = body.key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="Key cannot be empty")

    env_path = Path(".env")

    if env_path.exists():
        content = env_path.read_text()
        if re.search(r"^OPENAI_API_KEY\s*=", content, re.MULTILINE):
            content = re.sub(
                r"^OPENAI_API_KEY\s*=.*$",
                f"OPENAI_API_KEY={key}",
                content,
                flags=re.MULTILINE,
            )
        else:
            content += f"\nOPENAI_API_KEY={key}\n"
    else:
        content = f"OPENAI_API_KEY={key}\n"

    env_path.write_text(content)
    # Also update the running process so it takes effect immediately
    os.environ["OPENAI_API_KEY"] = key


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Liveness probe for Railway."""
    return {"status": "Tweet Engine running"}


# ---------------------------------------------------------------------------
# Static frontend — mounted last so API routes always win
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
