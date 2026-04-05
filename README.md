# Tweet Engine

Personal dashboard to manage multiple X (Twitter) accounts, generate
SEO-friendly tweets via OpenAI GPT-4o, and schedule them automatically.

## Stack

| Layer      | Technology          |
|------------|---------------------|
| Backend    | FastAPI + Python    |
| Database   | SQLite              |
| Scheduler  | APScheduler         |
| AI         | OpenAI GPT-4o       |
| Posting    | Tweepy v4           |
| Frontend   | Vanilla JS          |
| Hosting    | Railway             |

## Features

- **Multiple X accounts** — add, toggle, and manage accounts with individual tones
- **AI tweet generation** — paste a headline, get 5 variants (formal / casual / aggressive / analytical / satirical)
- **Auto-scheduler** — hourly queue processor posts due tweets automatically
- **Manual compose** — pick accounts, edit variants, schedule individually or all at once
- **Post history** — full log of every posting attempt with error details

## Local Setup

```bash
# 1. Clone
git clone <repo-url>
cd tweet-engine

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and fill in OPENAI_API_KEY

# 4. Run
uvicorn main:app --reload --port 8000

# 5. Open dashboard
open http://localhost:8000
```

## Railway Deployment

1. Push repo to GitHub
2. Create a new project on [Railway](https://railway.app) and connect the repo
3. Add the following environment variables in the Railway dashboard:

| Variable          | Value                              |
|-------------------|------------------------------------|
| `OPENAI_API_KEY`  | Your OpenAI key                    |
| `ALLOWED_ORIGINS` | `https://your-app.up.railway.app`  |
| `DB_PATH`         | `/data/tweet_engine.db` (with volume) or `tweet_engine.db` |

4. (Recommended) Add a Railway **Volume** mounted at `/data` and set `DB_PATH=/data/tweet_engine.db` so the database survives redeploys.

5. Railway will auto-detect `Procfile` and deploy.

## Project Structure

```
tweet-engine/
├── main.py            # FastAPI app, CORS, settings endpoints
├── database.py        # SQLite schema init
├── accounts.py        # Account CRUD API
├── news_topics.py     # News/topic CRUD API
├── tweet_generator.py # OpenAI GPT-4o integration
├── poster.py          # Tweepy posting + history API
├── scheduler.py       # APScheduler + queue API
├── frontend/
│   ├── style.css      # Shared stylesheet
│   ├── nav.js         # Shared sidebar + API helpers
│   ├── index.html     # Dashboard
│   ├── compose.html   # Compose workflow
│   ├── queue.html     # Queue manager
│   ├── history.html   # Post history
│   ├── accounts.html  # Account manager
│   └── settings.html  # Settings
├── Procfile
├── railway.json
├── requirements.txt
└── .env.example
```

## Notes

- **SQLite persistence on Railway**: SQLite data is lost on redeploy unless you attach a Railway Volume. For serious use, consider migrating to PostgreSQL (Railway offers a managed Postgres add-on).
- **CORS**: Set `ALLOWED_ORIGINS` to your Railway domain before deploying to restrict API access.
- **API docs**: Available at `http://localhost:8000/docs` when running locally.
