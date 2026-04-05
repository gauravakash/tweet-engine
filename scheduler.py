"""
scheduler.py — APScheduler queue manager + tweet queue API router.

The BackgroundScheduler runs inside the FastAPI process and is started/stopped
via the lifespan hook in main.py.

Scheduled job:
    process_queue()  — runs every 60 minutes, posts all due pending tweets

Endpoints:
    POST   /queue              — add single tweet to queue
    POST   /queue/bulk         — add bulk variants (staggered 5 min apart)
    GET    /queue              — list queue items (?status=pending|posted|failed)
    DELETE /queue/{id}         — remove a pending tweet
    POST   /queue/process-now  — manually trigger process_queue()
"""

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_connection
from poster import post_tweet

# ---------------------------------------------------------------------------
# Scheduler singleton — imported and controlled by main.py lifespan
# ---------------------------------------------------------------------------

scheduler = BackgroundScheduler()

router = APIRouter(prefix="/queue", tags=["Queue"])


# ---------------------------------------------------------------------------
# Core queue functions
# ---------------------------------------------------------------------------

def add_to_queue(
    account_id: int,
    tweet_text: str,
    video_url: str | None = None,
    scheduled_at: datetime | None = None,
) -> int:
    """
    Insert one tweet into tweet_queue with status='pending'.

    Args:
        scheduled_at: UTC datetime to post at. Defaults to now + 1 hour.

    Returns:
        The new queue row id.
    """
    if scheduled_at is None:
        scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)

    # Store as ISO-8601 string; strip tzinfo so SQLite comparison is consistent
    scheduled_str = scheduled_at.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO tweet_queue (account_id, tweet_text, video_url, scheduled_at)
            VALUES (?, ?, ?, ?)
            """,
            (account_id, tweet_text, video_url, scheduled_str),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def add_bulk_to_queue(
    variants: list[dict],
    video_url: str | None = None,
) -> list[int]:
    """
    Add multiple tweet variants to the queue, staggered 5 minutes apart so
    they don't all fire at the same time.

    Args:
        variants: list of {"account_id": int, "text": str, ...}
        video_url: optional URL appended to every tweet

    Returns:
        list of inserted queue row ids, in the same order as *variants*
    """
    base_time = datetime.now(timezone.utc) + timedelta(hours=1)
    ids = []

    for i, variant in enumerate(variants):
        scheduled_at = base_time + timedelta(minutes=5 * i)
        queue_id = add_to_queue(
            account_id=variant["account_id"],
            tweet_text=variant["text"],
            video_url=video_url,
            scheduled_at=scheduled_at,
        )
        ids.append(queue_id)

    return ids


def process_queue() -> dict:
    """
    Scheduled job — runs every 60 minutes.

    Fetches all pending tweets whose scheduled_at has passed, posts them via
    Tweepy, and updates their status in tweet_queue accordingly.

    Returns a summary dict (also printed for log visibility).
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        due_rows = conn.execute(
            """
            SELECT id, account_id, tweet_text, video_url
            FROM   tweet_queue
            WHERE  status = 'pending'
            AND    scheduled_at <= ?
            ORDER  BY scheduled_at ASC
            """,
            (now_str,),
        ).fetchall()
    finally:
        conn.close()

    total = len(due_rows)
    succeeded = 0
    failed = 0

    for row in due_rows:
        result = post_tweet(
            account_id=row["account_id"],
            tweet_text=row["tweet_text"],
            video_url=row["video_url"],
        )
        new_status = "posted" if result["success"] else "failed"

        conn = get_connection()
        try:
            conn.execute(
                "UPDATE tweet_queue SET status = ? WHERE id = ?",
                (new_status, row["id"]),
            )
            conn.commit()
        finally:
            conn.close()

        if result["success"]:
            succeeded += 1
        else:
            failed += 1
            print(
                f"[scheduler] FAILED queue_id={row['id']} "
                f"account_id={row['account_id']}: {result['error']}"
            )

    summary = {"processed": total, "succeeded": succeeded, "failed": failed}
    print(f"[scheduler] process_queue complete — {summary}")
    return summary


def get_queue(status: str | None = None) -> list[dict]:
    """
    Return up to 50 queue items, optionally filtered by status.
    Joins with accounts to include username and tone.

    Args:
        status: "pending" | "posted" | "failed" | None (all)
    """
    conn = get_connection()
    try:
        if status:
            rows = conn.execute(
                """
                SELECT q.id, q.account_id, a.username, a.tone,
                       q.tweet_text, q.video_url, q.scheduled_at,
                       q.status, q.created_at
                FROM   tweet_queue q
                JOIN   accounts    a ON a.id = q.account_id
                WHERE  q.status = ?
                ORDER  BY q.scheduled_at ASC
                LIMIT  50
                """,
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT q.id, q.account_id, a.username, a.tone,
                       q.tweet_text, q.video_url, q.scheduled_at,
                       q.status, q.created_at
                FROM   tweet_queue q
                JOIN   accounts    a ON a.id = q.account_id
                ORDER  BY q.scheduled_at ASC
                LIMIT  50
                """,
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_from_queue(queue_id: int) -> None:
    """
    Delete a tweet from the queue.

    Raises:
        ValueError: if the tweet is not found or is not in 'pending' status.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, status FROM tweet_queue WHERE id = ?", (queue_id,)
        ).fetchone()

        if row is None:
            raise ValueError(f"Queue item {queue_id} not found")
        if row["status"] != "pending":
            raise ValueError(
                f"Cannot delete queue item {queue_id} — "
                f"status is '{row['status']}', only 'pending' items can be removed"
            )

        conn.execute("DELETE FROM tweet_queue WHERE id = ?", (queue_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# APScheduler job registration
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    """Add the process_queue job and start the scheduler."""
    scheduler.add_job(
        process_queue,
        trigger="interval",
        minutes=60,
        id="process_queue",
        replace_existing=True,
        misfire_grace_time=600,  # 10-minute grace window
    )
    scheduler.start()
    print("[scheduler] Started — process_queue fires every 60 minutes")


def shutdown_scheduler() -> None:
    """Gracefully stop the scheduler (waits for running jobs to finish)."""
    scheduler.shutdown(wait=True)
    print("[scheduler] Stopped")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class QueueItemIn(BaseModel):
    account_id: int
    tweet_text: str
    video_url: str | None = None
    scheduled_at: datetime | None = None  # ISO-8601; None → now + 1 hour


class BulkVariant(BaseModel):
    account_id: int
    text: str


class BulkQueueIn(BaseModel):
    variants: list[BulkVariant]
    video_url: str | None = None


class QueueItemOut(BaseModel):
    id: int
    account_id: int
    username: str
    tone: str | None
    tweet_text: str
    video_url: str | None
    scheduled_at: str
    status: str
    created_at: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def enqueue_single(body: QueueItemIn):
    """Add one tweet to the queue."""
    queue_id = add_to_queue(
        account_id=body.account_id,
        tweet_text=body.tweet_text,
        video_url=body.video_url,
        scheduled_at=body.scheduled_at,
    )
    return {"queue_id": queue_id}


@router.post("/bulk", status_code=201)
def enqueue_bulk(body: BulkQueueIn):
    """Add multiple tweet variants, staggered 5 minutes apart."""
    variants = [v.model_dump() for v in body.variants]
    ids = add_bulk_to_queue(variants=variants, video_url=body.video_url)
    return {"queue_ids": ids, "count": len(ids)}


@router.get("", response_model=list[QueueItemOut])
def list_queue(status: str | None = Query(default=None)):
    """
    Return up to 50 queue items joined with account info.
    Optionally filter by ?status=pending|posted|failed
    """
    valid_statuses = {"pending", "posted", "failed", None}
    if status not in valid_statuses:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{status}'. Use: pending, posted, or failed",
        )
    return get_queue(status=status)


@router.delete("/{queue_id}", status_code=204)
def remove_from_queue(queue_id: int):
    """Remove a pending tweet from the queue."""
    try:
        delete_from_queue(queue_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/process-now")
def trigger_process_now():
    """Manually trigger process_queue() without waiting for the next interval."""
    summary = process_queue()
    return summary
