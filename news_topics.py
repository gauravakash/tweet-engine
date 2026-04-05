"""
news_topics.py — CRUD router for the news_topics table.

Endpoints:
    POST   /topics        — add a headline
    GET    /topics        — list latest 20 headlines
    DELETE /topics/{id}   — remove a headline
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_connection

router = APIRouter(prefix="/topics", tags=["News Topics"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class TopicIn(BaseModel):
    headline: str
    source_url: str | None = None


class TopicOut(BaseModel):
    id: int
    headline: str
    source_url: str | None
    created_at: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=TopicOut, status_code=201)
def create_topic(body: TopicIn):
    """Save a new headline/topic to the database."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO news_topics (headline, source_url) VALUES (?, ?)",
            (body.headline, body.source_url),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM news_topics WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.get("", response_model=list[TopicOut])
def list_topics():
    """Return the 20 most recently added topics."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM news_topics ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.delete("/{topic_id}", status_code=204)
def delete_topic(topic_id: int):
    """Delete a topic by id. Returns 404 if not found."""
    conn = get_connection()
    try:
        result = conn.execute(
            "DELETE FROM news_topics WHERE id = ?", (topic_id,)
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Topic not found")
    finally:
        conn.close()
