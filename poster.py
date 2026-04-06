"""
poster.py — Tweepy v4 posting logic for Tweet Engine.

Public API:
    get_tweepy_client(account_id)             -> tweepy.Client
    post_tweet(account_id, tweet_text, ...)   -> dict
    post_to_all_accounts(tweet_texts, ...)    -> list[dict]

Router:
    GET /history  — paginated post_history joined with accounts
"""

import tweepy
from fastapi import APIRouter, Query

from database import get_connection

router = APIRouter(prefix="/history", tags=["History"])


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def get_tweepy_client(account_id: int) -> tweepy.Client:
    """
    Fetch credentials for *account_id* from the DB and return an authenticated
    Tweepy v4 Client.

    Raises:
        ValueError: if the account doesn't exist or is inactive.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, username, is_active,
                   api_key, api_secret, access_token, access_secret
            FROM accounts
            WHERE id = ?
            """,
            (account_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise ValueError(f"Account {account_id} not found")
    if not row["is_active"]:
        raise ValueError(f"Account '{row['username']}' (id={account_id}) is inactive")

    # Log credential presence (never log actual values)
    print(
        f"[poster] Building Tweepy client for account {account_id} (@{row['username']}) — "
        f"api_key={'set' if row['api_key'] else 'MISSING'}, "
        f"api_secret={'set' if row['api_secret'] else 'MISSING'}, "
        f"access_token={'set' if row['access_token'] else 'MISSING'}, "
        f"access_secret={'set' if row['access_secret'] else 'MISSING'}"
    )

    return tweepy.Client(
        consumer_key=row["api_key"],
        consumer_secret=row["api_secret"],
        access_token=row["access_token"],
        access_token_secret=row["access_secret"],
    )


# ---------------------------------------------------------------------------
# Single-account poster
# ---------------------------------------------------------------------------

def post_tweet(
    account_id: int,
    tweet_text: str,
    video_url: str | None = None,
) -> dict:
    """
    Post a tweet from the account identified by *account_id*.

    If *video_url* is provided it is appended to the tweet text on a new line.
    Every attempt (success or failure) is recorded in post_history.

    Returns:
        {
            "success":  bool,
            "tweet_id": str | None,   # X tweet id on success
            "error":    str | None,   # error message on failure
        }
    """
    # Append video URL when provided
    final_text = f"{tweet_text}\n{video_url}" if video_url else tweet_text

    tweet_id: str | None = None
    error_msg: str | None = None
    success = False

    try:
        client = get_tweepy_client(account_id)
        # user_auth=True forces OAuth 1.0a (consumer key + access token).
        # The default (False) uses App-Only Bearer Token, which cannot post tweets.
        response = client.create_tweet(text=final_text, user_auth=True)
        tweet_id = str(response.data["id"])
        success = True
    except Exception as exc:
        print(f"[poster] Test post error: {type(exc).__name__}: {exc}")
        # Tweepy errors sometimes have empty str() — try multiple sources
        error_msg = (
            getattr(exc, "api_messages", None)
            or getattr(exc, "reason", None)
            or str(exc)
            or type(exc).__name__
        )
        # api_messages is a list on Tweepy errors — flatten to string
        if isinstance(error_msg, list):
            error_msg = "; ".join(str(m) for m in error_msg) or type(exc).__name__

    # ------------------------------------------------------------------
    # Log result to post_history regardless of outcome
    # ------------------------------------------------------------------
    _log_post_history(
        account_id=account_id,
        tweet_text=final_text,
        video_url=video_url,
        status="posted" if success else "failed",
        error_message=error_msg,
    )

    return {"success": success, "tweet_id": tweet_id, "error": error_msg}


# ---------------------------------------------------------------------------
# Multi-account bulk poster
# ---------------------------------------------------------------------------

def post_to_all_accounts(
    tweet_texts: list[dict],
    video_url: str | None = None,
) -> list[dict]:
    """
    Post a tweet from each entry in *tweet_texts*.

    Args:
        tweet_texts: list of {"account_id": int, "text": str}
        video_url:   optional URL appended to every tweet

    Returns:
        list of results from post_tweet(), each augmented with "account_id"
    """
    results = []
    for item in tweet_texts:
        result = post_tweet(
            account_id=item["account_id"],
            tweet_text=item["text"],
            video_url=video_url,
        )
        result["account_id"] = item["account_id"]
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# History endpoint
# ---------------------------------------------------------------------------

@router.get("")
def get_history(
    account_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
):
    """
    Return paginated post_history rows joined with account username and tone.

    Args:
        account_id: optional filter by account
        page:       1-based page number (20 rows per page)
    """
    limit  = 20
    offset = (page - 1) * limit

    conn = get_connection()
    try:
        if account_id:
            rows = conn.execute(
                """
                SELECT h.id, a.username, a.tone,
                       h.tweet_text, h.video_url,
                       h.posted_at, h.status, h.error_message
                FROM   post_history h
                JOIN   accounts     a ON a.id = h.account_id
                WHERE  h.account_id = ?
                ORDER  BY h.posted_at DESC
                LIMIT  ? OFFSET ?
                """,
                (account_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT h.id, a.username, a.tone,
                       h.tweet_text, h.video_url,
                       h.posted_at, h.status, h.error_message
                FROM   post_history h
                JOIN   accounts     a ON a.id = h.account_id
                ORDER  BY h.posted_at DESC
                LIMIT  ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _log_post_history(
    account_id: int,
    tweet_text: str,
    video_url: str | None,
    status: str,
    error_message: str | None,
) -> None:
    """Insert one row into post_history. Swallows its own errors to avoid
    masking the original tweet-posting result."""
    try:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO post_history
                (account_id, tweet_text, video_url, status, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (account_id, tweet_text, video_url, status, error_message),
        )
        conn.commit()
        conn.close()
    except Exception as log_exc:  # noqa: BLE001
        print(f"[poster] WARNING: could not write post_history — {log_exc}")
