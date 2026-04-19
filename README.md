# Scalable Social Data Aggregator

**Batch-scheduled Reddit demand intelligence, powered by webhook-driven serverless architecture.**

An open-source monorepo that pairs a [Reddit Devvit](https://developers.reddit.com/) scheduler app with a Python/Flask intelligence backend. The Devvit app runs a daily scheduled job to scan subreddit posts for demand-intent signals, batches the matches, and fires a single webhook to the backend — which runs Gemini-powered SWOT and sentiment analysis and streams results to a live dashboard.

> **Bring Your Own Subreddit** — install the sensor on _any_ subreddit you moderate and point it at your own backend instance.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          MONOREPO ROOT                              │
├──────────────────────────┬──────────────────────────────────────────┤
│  /scalable-social/       │  /intelligence-backend/                  │
│  (Devvit Scheduler App)  │  (Python/Flask + Celery + PostgreSQL)    │
│                          │                                          │
│  TypeScript + React      │  backend/                                │
│  webview dashboard       │    app/api.py        ← webhook receiver  │
│                          │    app/analysis_tasks.py ← Gemini analysis   │
│  Daily scheduler job     │    app/models.py     ← PostgreSQL ORM    │
│  scans posts, filters    │  docker-compose.yml                      │
│  by intent regex,        │  requirements.txt                        │
│  batches matches into    │  .env.example                            │
│  a single POST to:      │                                          │
│  /api/v1/webhooks/devvit │                                          │
└──────────┬───────────────┴──────────────────┬───────────────────────┘
           │                                  │
           │   HTTPS POST (JSON batch array)  │
           └─────────────────────────────────►│
                                              │
                             ┌────────────────▼──────────────┐
                             │  Flask API (port 8000)         │
                             │  Returns 202 Accepted          │
                             │  Dispatches batch to Celery    │
                             └────────────────┬──────────────┘
                                              │
                             ┌────────────────▼──────────────┐
                             │  Celery Worker                 │
                             │  Iterates batch items          │
                             │  Gemini 1.5 Flash SWOT (each)  │
                             │  Save to PostgreSQL            │
                             │  Emit Socket.IO events         │
                             └───────────────────────────────┘
```

### Data Flow

1. The **Devvit scheduler** (`/scalable-social/`) runs a `daily_demand_scan` job every 24 hours (6:00 AM UTC).
2. The job fetches up to 100 recent posts from the installed subreddit via the Reddit API.
3. Posts from the last 24 hours are filtered through a demand-intent regex.
4. Matching posts increment **Redis category counters** for the in-app leaderboard.
5. All matches are compiled into a **single JSON batch array** and dispatched via `fetch()` POST to the backend webhook.
6. The **Flask API** (`/intelligence-backend/`) returns `202 Accepted` immediately.
7. A **Celery worker** iterates the batch, running Gemini SWOT analysis on each item.
8. Derived intelligence (title, summary, SWOT, opportunity rating, defeat strategy) is saved to PostgreSQL. **Raw Reddit text is never stored.**
9. **Socket.IO** events push new ideas to the live dashboard in real time.

---

## Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Docker](https://docs.docker.com/get-docker/) | 24+ | Container runtime |
| [Node.js](https://nodejs.org/) | 18+ | Devvit CLI runtime |
| [Devvit CLI](https://developers.reddit.com/docs/get-started) | latest | Reddit app development |

### 1. Start the Intelligence Backend

```bash
cd intelligence-backend/

# Create your environment file
cp .env.example .env
# Edit .env — fill in POSTGRES_PASSWORD, SECRET_KEY, and GOOGLE_API_KEY

# Build and launch all services
docker compose up --build -d

# Verify services are healthy
curl http://localhost:8000/api/v1/status

# Generate initial database migration
docker compose exec backend flask db migrate -m "initial"
docker compose exec backend flask db upgrade
```

### 2. Expose the Backend via Static HTTPS Domain

> [!IMPORTANT]
> The Devvit scheduler dispatches webhooks to a **static HTTPS endpoint**. Running `docker compose` locally requires a persistent HTTPS domain mapped to your local port 8000. A [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) is the recommended approach for production-grade zero-trust ingress.

**Option A: Cloudflare Tunnel (recommended for production)**
```bash
# Install cloudflared
# See: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/

# Create a tunnel mapped to your domain
cloudflared tunnel --url http://localhost:8000
# Or configure a named tunnel with a static subdomain:
cloudflared tunnel route dns <TUNNEL_ID> webhook.yourdomain.com
```

**Option B: ngrok (development only)**
```bash
ngrok http 8000
# Note: free ngrok URLs are ephemeral — they change on restart.
# Use a reserved domain (paid) or Cloudflare Tunnel for stability.
```

The Devvit app is configured to send webhooks to:
```
https://webhook.legacysweatequity.com/api/webhooks/devvit
```

If self-hosting, update the `WEBHOOK_URL` constant in `/scalable-social/src/main.tsx` to your own static HTTPS domain.

### 3. Install the Devvit App

```bash
cd scalable-social/

# Install dependencies
npm install

# Log in to the Devvit CLI
npx devvit login

# Start a playtest on your test subreddit
npx devvit playtest r/YOUR_TEST_SUBREDDIT
```

On install, the app automatically schedules the `daily_demand_scan` job to run at 6:00 AM UTC.

### 4. Test the Pipeline

The scheduler runs automatically every 24 hours. To test immediately:
1. Create several posts in your test subreddit containing demand signals:
   > _"I wish there was an app that could track my houseplants' watering schedule"_
   >
   > _"Somebody should make a tool for comparing apartment leases side by side"_
2. Trigger the scheduler manually via the Devvit CLI (or wait for the next scheduled run).
3. Check the Celery worker logs for Gemini analysis output.
4. View processed ideas on the dashboard at `http://localhost:8000`.

---

## Project Structure

```
scalable-social-data-aggregator/
├── intelligence-backend/           # Python/Flask intelligence engine
│   ├── backend/
│   │   ├── app/
│   │   │   ├── __init__.py         # Flask app factory
│   │   │   ├── api.py              # Webhook receiver (batched)
│   │   │   ├── analysis_tasks.py   # Celery tasks (batch + Gemini)
│   │   │   ├── extensions.py       # DB, Redis, Socket.IO instances
│   │   │   ├── models.py           # SQLAlchemy ORM models
│   │   │   ├── main.py             # Dashboard blueprint
│   │   │   └── events.py           # Socket.IO event handlers
│   │   ├── celery_app.py           # Celery application config
│   │   ├── worker.py               # Celery worker entry point
│   │   ├── wsgi.py                 # Gunicorn WSGI entry point
│   │   ├── config.py               # Environment-based config
│   │   └── Dockerfile              # Python 3.12 slim image
│   ├── docker-compose.yml          # Full stack orchestration
│   ├── entrypoint.sh               # DB migration runner
│   ├── requirements.txt            # Python dependencies
│   ├── Makefile                    # Secret generation helpers
│   └── .env.example                # Environment template
│
├── scalable-social/                # Reddit Devvit scheduler app
│   ├── src/
│   │   ├── main.tsx                # Scheduler job + intent filter
│   │   └── client/
│   │       └── index.html          # Webview dashboard (leaderboard)
│   ├── package.json
│   ├── tsconfig.json
│   └── devvit.json                 # Devvit app manifest
│
├── PRIVACY_POLICY.md               # Data handling transparency
├── TERMS_OF_SERVICE.md             # Usage terms
├── README.md                       # ← You are here
└── .gitignore
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_USER` | Yes | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `POSTGRES_DB` | Yes | PostgreSQL database name |
| `SECRET_KEY` | Yes | Flask session secret |
| `CELERY_BROKER_URL` | Yes | Redis URL for Celery broker |
| `CELERY_RESULT_BACKEND_URL` | Yes | Redis URL for Celery results |
| `GOOGLE_API_KEY` | Yes | Google AI (Gemini) API key |
| `DEVVIT_WEBHOOK_SECRET` | No | Shared secret for webhook auth |
| `UID` / `GID` | Yes | Host user/group IDs for Docker |

---

## Webhook API Reference

### `POST /api/v1/webhooks/devvit`

Receives a batched array of demand-signal posts from the Devvit scheduler.

**Request Body (batch):**
```json
[
  {
    "title": "I wish there was an app for...",
    "body": "Full post body text here",
    "subreddit": "AppIdeas"
  },
  {
    "title": "Somebody should make a tool that...",
    "body": "Another post body",
    "subreddit": "AppIdeas"
  }
]
```

**Response:** `202 Accepted`
```json
{
  "status": "accepted",
  "batch_size": 2
}
```

The batch is processed asynchronously by a Celery worker — the endpoint returns immediately to prevent Devvit `fetch()` timeout drops. A single-object payload is also accepted (auto-wrapped into a batch of 1).

---

## Compliance

- [Privacy Policy](PRIVACY_POLICY.md) — Details on data processing, retention, and third-party services.
- [Terms of Service](TERMS_OF_SERVICE.md) — Usage terms, operator responsibilities, and disclaimers.

**Key guarantee:** Raw Reddit post text is processed in-memory only and is **never persisted** to the database. Only AI-derived intelligence summaries are stored.

---

## License

This project is open source. See [LICENSE](LICENSE) for details.