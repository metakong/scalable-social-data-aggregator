# Scalable Social Data Aggregator

**Real-time Reddit demand intelligence, powered by event-driven webhooks.**

An open-source monorepo that pairs a [Reddit Devvit](https://developers.reddit.com/) sensor app with a Python/Flask intelligence backend. The Devvit app intercepts posts matching demand-intent patterns in real time and fires webhooks to the backend, which runs Gemini-powered SWOT and sentiment analysis and streams results to a live dashboard.

> **Bring Your Own Subreddit** — install the sensor on _any_ subreddit you moderate and point it at your own backend instance.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MONOREPO ROOT                            │
├─────────────────────┬───────────────────────────────────────────┤
│  /scalable-social/  │  /intelligence-backend/                   │
│  (Devvit Sensor)    │  (Python/Flask + Celery + PostgreSQL)     │
│                     │                                           │
│  TypeScript app     │  backend/                                 │
│  installed on a     │    app/api.py        ← webhook receiver   │
│  subreddit via      │    app/cpo_tasks.py  ← Gemini analysis    │
│  Devvit CLI         │    app/models.py     ← PostgreSQL ORM     │
│                     │  docker-compose.yml                       │
│  Fires POST         │  requirements.txt                         │
│  /api/v1/webhooks/  │  .env.example                             │
│  devvit on match    │                                           │
└─────────┬───────────┴────────────────┬──────────────────────────┘
          │                            │
          │   HTTP POST (JSON)         │
          └───────────────────────────►│
                                       │
                          ┌────────────▼────────────┐
                          │  Flask API (port 8000)   │
                          │  Returns 202 Accepted    │
                          │  Dispatches to Celery    │
                          └────────────┬────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │  Celery Worker           │
                          │  Gemini 1.5 Flash SWOT   │
                          │  Save to PostgreSQL      │
                          │  Emit Socket.IO event    │
                          └─────────────────────────┘
```

### Data Flow

1. A user posts in a monitored subreddit.
2. The **Devvit sensor** (`/scalable-social/`) intercepts the `PostSubmit` event.
3. A regex intent filter checks for demand signals (e.g. _"wish there was an app"_, _"somebody should make"_).
4. On match, the sensor `fetch()`es a POST to the intelligence backend webhook.
5. The **Flask API** (`/intelligence-backend/`) returns `202 Accepted` immediately.
6. A **Celery worker** picks up the payload and runs Gemini analysis.
7. Derived intelligence (title, summary, SWOT, opportunity rating, defeat strategy) is saved to PostgreSQL. **Raw Reddit text is never stored.**
8. A **Socket.IO** event pushes the new idea to the live dashboard.

---

## Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Docker](https://docs.docker.com/get-docker/) | 24+ | Container runtime |
| [ngrok](https://ngrok.com/) | 3+ | Expose local port to the internet |
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
```

### 2. Expose the Backend with ngrok

```bash
ngrok http 8000
```

Copy the resulting HTTPS forwarding URL (e.g. `https://abc123.ngrok.io`).

### 3. Install the Devvit Sensor

```bash
cd scalable-social/

# Install dependencies
npm install

# Log in to the Devvit CLI
npx devvit login

# Start a playtest on your test subreddit
npx devvit playtest r/YOUR_TEST_SUBREDDIT
```

When prompted for **app settings**, paste your ngrok URL as the webhook URL:

```
https://abc123.ngrok.io/api/v1/webhooks/devvit
```

### 4. Test the Pipeline

Create a post in your test subreddit containing a demand signal:

> _"I wish there was an app that could track my houseplants' watering schedule"_

Within seconds you should see:
- A `202 Accepted` response in your ngrok console
- Celery worker logs showing Gemini analysis
- A new idea card on the dashboard at `http://localhost:8000`

---

## Project Structure

```
scalable-social-data-aggregator/
├── intelligence-backend/           # Python/Flask intelligence engine
│   ├── backend/
│   │   ├── app/
│   │   │   ├── __init__.py         # Flask app factory
│   │   │   ├── api.py              # Webhook receiver + REST API
│   │   │   ├── cpo_tasks.py        # Celery tasks (Gemini analysis)
│   │   │   ├── extensions.py       # DB, Redis, Socket.IO instances
│   │   │   ├── models.py           # SQLAlchemy ORM models
│   │   │   ├── main.py             # Dashboard blueprint
│   │   │   └── events.py           # Socket.IO event handlers
│   │   ├── celery_app.py           # Celery application config
│   │   ├── worker.py               # Celery worker entry point
│   │   ├── wsgi.py                 # Gunicorn WSGI entry point
│   │   ├── config.py               # Environment-based configuration
│   │   └── Dockerfile              # Python 3.12 slim image
│   ├── docker-compose.yml          # Full stack orchestration
│   ├── entrypoint.sh               # DB migration runner
│   ├── requirements.txt            # Python dependencies
│   ├── Makefile                    # Secret generation helpers
│   └── .env.example                # Environment template
│
├── scalable-social/                # Reddit Devvit sensor app
│   ├── src/
│   │   └── main.tsx                # PostSubmit trigger + intent filter
│   ├── package.json
│   ├── tsconfig.json
│   └── devvit.yaml                 # Devvit app manifest
│
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

Receives demand-signal posts from the Devvit sensor.

**Request Body:**
```json
{
  "title": "I wish there was an app for...",
  "body": "Full post body text here",
  "subreddit": "AppIdeas"
}
```

**Response:** `202 Accepted`
```json
{
  "status": "accepted"
}
```

The payload is processed asynchronously — the endpoint returns immediately to prevent Devvit `fetch()` timeout drops.

---

## License

This project is open source. See [LICENSE](LICENSE) for details.