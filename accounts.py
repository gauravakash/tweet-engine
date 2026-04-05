"""
accounts.py — CRUD router for X account management.

Secrets (api_key, api_secret, access_token, access_secret) are written to the
database but are NEVER returned in any API response.

Endpoints:
    POST   /accounts                  — add a new account
    GET    /accounts                  — list all accounts (no secrets)
    PATCH  /accounts/{id}/toggle      — flip is_active on/off
    DELETE /accounts/{id}             — remove account
    POST   /accounts/test-post/{id}   — post a test tweet from this account
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_connection

router = APIRouter(prefix="/accounts", tags=["Accounts"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AccountIn(BaseModel):
    username: str
    tone: str                        # formal | casual | aggressive | analytical | satirical
    persona_description: str
    api_key: str
    api_secret: str
    access_token: str
    access_secret: str


class AccountSummary(BaseModel):
    """Safe public view — no secrets."""
    id: int
    username: str
    tone: str | None
    persona_description: str | None
    is_active: int
    created_at: str


class AccountCreated(BaseModel):
    """Minimal response on creation — no secrets."""
    id: int
    username: str
    tone: str | None
    is_active: int


class ToggleResponse(BaseModel):
    id: int
    username: str
    is_active: int


class TestPostBody(BaseModel):
    text: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=AccountCreated, status_code=201)
def create_account(body: AccountIn):
    """Store a new X account with its API credentials."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO accounts
                (username, tone, persona_description,
                 api_key, api_secret, access_token, access_secret)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.username,
                body.tone,
                body.persona_description,
                body.api_key,
                body.api_secret,
                body.access_token,
                body.access_secret,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, username, tone, is_active FROM accounts WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(row)
    except Exception as exc:
        # Unique constraint on username will surface here
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("", response_model=list[AccountSummary])
def list_accounts():
    """Return all accounts — secrets excluded."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, username, tone, persona_description, is_active, created_at
            FROM accounts
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.patch("/{account_id}/toggle", response_model=ToggleResponse)
def toggle_active(account_id: int):
    """Flip is_active between 1 (active) and 0 (paused) for an account."""
    conn = get_connection()
    try:
        result = conn.execute(
            "UPDATE accounts SET is_active = 1 - is_active WHERE id = ?",
            (account_id,),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Account not found")
        row = conn.execute(
            "SELECT id, username, is_active FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int):
    """Delete an account (cascades to tweet_queue and post_history)."""
    conn = get_connection()
    try:
        result = conn.execute(
            "DELETE FROM accounts WHERE id = ?", (account_id,)
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Account not found")
    finally:
        conn.close()


@router.post("/test-post/{account_id}")
def test_post(account_id: int, body: TestPostBody):
    """Post a test tweet from a specific account."""
    # Import here to avoid a circular import (poster imports from accounts indirectly)
    from poster import post_tweet

    result = post_tweet(account_id, body.text)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result["error"])
    return result
