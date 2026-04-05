"""
database.py — SQLite schema setup for Tweet Engine.

Creates all tables on first run; safe to call multiple times (uses IF NOT EXISTS).
"""

import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "tweet_engine.db")


def get_connection() -> sqlite3.Connection:
    """Return a connection with foreign key enforcement enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row  # allows dict-like column access
    return conn


def init_db() -> None:
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # ------------------------------------------------------------------
    # accounts — one row per managed X/Twitter account
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            username            TEXT    NOT NULL UNIQUE,
            tone                TEXT,                       -- e.g. "casual", "professional"
            persona_description TEXT,                       -- freeform prompt context
            api_key             TEXT    NOT NULL,
            api_secret          TEXT    NOT NULL,
            access_token        TEXT    NOT NULL,
            access_secret       TEXT    NOT NULL,
            is_active           INTEGER NOT NULL DEFAULT 1, -- 1 = active, 0 = paused
            created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ------------------------------------------------------------------
    # tweet_queue — tweets waiting to be posted
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tweet_queue (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            tweet_text   TEXT    NOT NULL,
            video_url    TEXT,                              -- optional attached video
            scheduled_at TEXT    NOT NULL,                  -- ISO-8601 UTC datetime
            status       TEXT    NOT NULL DEFAULT 'pending' -- pending | posted | failed
                         CHECK(status IN ('pending', 'posted', 'failed')),
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ------------------------------------------------------------------
    # post_history — immutable log of every posting attempt
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS post_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            tweet_text    TEXT    NOT NULL,
            video_url     TEXT,
            posted_at     TEXT    NOT NULL DEFAULT (datetime('now')),
            status        TEXT    NOT NULL CHECK(status IN ('posted', 'failed')),
            error_message TEXT                              -- populated on failure
        )
    """)

    # ------------------------------------------------------------------
    # news_topics — headlines fed into the AI generation pipeline
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_topics (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            headline   TEXT NOT NULL,
            source_url TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print(f"[database] Tables ready — {DB_PATH}")
