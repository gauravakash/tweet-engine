# Tweet Engine — Progress

## Status: COMPLETE ✅

---

## Stack

| Layer      | Technology      |
|------------|-----------------|
| Backend    | FastAPI         |
| Database   | SQLite          |
| Scheduler  | APScheduler     |
| AI         | OpenAI GPT-4o   |
| Posting    | Tweepy v4       |
| Frontend   | Vanilla JS      |
| Hosting    | Railway         |

---

## Built

- [x] `database.py` — SQLite schema: `accounts`, `tweet_queue`, `post_history`, `news_topics`
- [x] `main.py` — FastAPI app, CORS (env-configurable), DB init, scheduler start/stop, settings endpoints, frontend served at `/`
- [x] `news_topics.py` — `POST /topics`, `GET /topics`, `DELETE /topics/{id}`
- [x] `llm_config.py` — LangChain `get_llm()` factory; model set via `OPENAI_MODEL` env var ✅
- [x] `tweet_generator.py` — refactored to LangChain LCEL (`prompt | llm | JsonOutputParser`); async; model-agnostic ✅
- [x] `accounts.py` — account CRUD + `POST /accounts/test-post/{id}`; secrets never returned; Excel/CSV bulk import ✅
- [x] `poster.py` — Tweepy posting, `post_history` logging, `GET /history`
- [x] `scheduler.py` — APScheduler (60 min), `add_to_queue()`, `add_bulk_to_queue()`, queue CRUD at `/queue`
- [x] `frontend/style.css` — shared stylesheet (CSS variables, all components)
- [x] `frontend/nav.js` — sidebar, toast, API helper, shared utilities
- [x] `frontend/index.html` — Dashboard (stats, accounts strip, quick compose, recent topics)
- [x] `frontend/compose.html` — Full compose (multi-account, generate, edit, schedule)
- [x] `frontend/queue.html` — Queue (filter, delete, manual trigger)
- [x] `frontend/history.html` — Post history (account filter, pagination)
- [x] `frontend/accounts.html` — Account management (add, toggle, test, delete)
- [x] `frontend/settings.html` — Settings (OpenAI key, scheduler, API status)
- [x] `Procfile` — Railway start command
- [x] `railway.json` — Railway build + deploy config
- [x] `.gitignore` — excludes `.env`, `*.db`, `__pycache__`, etc.
- [x] `runtime.txt` — Python 3.11.0
- [x] `.env.example` — all required env variables documented
- [x] `README.md` — setup, deploy, and project structure docs
- [x] `llm_config.py` + `tweet_generator.py` refactored to LangChain LCEL — model-agnostic (change `OPENAI_MODEL` env var to swap models, no code changes needed)

---

## Deployment

- **Railway URL:** *(add after deploy)*
- **Environment variables:** set in Railway dashboard (see `.env.example`)

---

## Known Issues

- SQLite is not persistent if Railway restarts without a Volume mount.
  Fix: add a Railway Volume at `/data` and set `DB_PATH=/data/tweet_engine.db`
- For high-volume production use: migrate to PostgreSQL (Railway managed add-on available)
