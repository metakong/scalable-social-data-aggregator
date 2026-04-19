# Scalable Social Data Aggregator

**An asynchronous, webhook-driven data pipeline bridging serverless TypeScript applications with a Python/Flask intelligence backend.**

This monorepo is designed as an open-source proof-of-work demonstrating end-to-end orchestration of serverless event triggers, secure REST APIs, asynchronous task queues, and Generative AI inference. 

The architecture consists of a [Reddit Devvit](https://developers.reddit.com/) scheduled sensor that extracts community trend signals and securely transmits them to an isolated Python backend. The backend utilizes Google's Gemini 2.5 Flash Lite to process the text into an Open Source Research Summary without retaining raw user data.

---

## 🏗 Architecture Overview

The repository is divided into two distinct, decoupled environments:

```text
┌─────────────────────────────────────────────────────────────────────┐
│                          MONOREPO ROOT                              │
├──────────────────────────┬──────────────────────────────────────────┤
│  /scalable-social/       │  /intelligence-backend/                  │
│  (Devvit Sensor App)     │  (Python/Flask + Celery + PostgreSQL)    │
│                          │                                          │
│  TypeScript + React      │  backend/                                │
│  webview dashboard       │    app/api.py        ← HMAC Webhook Auth │
│                          │    app/analysis_tasks.py ← Gemini 2.5    │
│  Daily scheduler job     │    app/models.py     ← PostgreSQL ORM    │
│  scans posts, filters    │  docker-compose.yml                      │
│  by intent regex,        │                                          │
│  updates Redis metrics,  │  4-Container Stack:                      │
│  and fires HTTP webhook. │  Flask API, Celery Worker, Redis, DB     │
└──────────────────────────┴──────────────────────────────────────────┘

### **The Webhook Lifecycle (Data Flow)**

1. **Extraction (Serverless Cron):** A Devvit scheduled job executes daily, fetching the last 24 hours of subreddit posts and applying a regex filter to isolate specific trend themes.  
2. **Transmission (Secure Edge):** Matched posts are batched into a JSON array and transmitted via an HTTP POST webhook. The request is secured using a dynamic Authorization header.  
3. **Ingestion (Stateless API):** The Flask API receives the payload, verifies the HMAC SHA-256 signature, and instantly returns a 202 Accepted to bypass serverless execution timeouts. The batch is dispatched to Redis.  
4. **Analysis (Async Queue):** A persistent Celery worker iterates through the batch, executing inference via the google-genai SDK (gemini-2.5-flash-lite) to generate categorical research summaries and competitor analysis.  
5. **Data Minimization:** Derived intelligence is persisted to PostgreSQL. **Raw Reddit text is permanently discarded in memory and never stored.**  
6. **Real-time UI:** Socket.IO events push updates back to the frontend dashboards.

## ---

**🛠 Engineering Highlights (Tech Stack)**

This repository serves to demonstrate practical, production-ready implementation of the following technologies and methodologies:

* **Backend:** Python 3.12, Flask, SQLAlchemy, Celery, PostgreSQL, Redis.  
* **Frontend / Serverless:** Node.js, TypeScript, React, Devvit SDK.  
* **AI / ML Integration:** LLM Orchestration via the modern google-genai SDK (Inference only, no model training).  
* **Systems Architecture:** Docker Compose containerization, Webhook design, Event-driven Background Workers, Constant-time HMAC Security.  
* **Compliance Engineering:** Strict adherence to Data Minimization principles (GDPR/CCPA mindset) and platform TOS constraints.

## ---

**🚀 Open-Source Deployment Guide**

Developers can fork this repository to run their own Trend Analysis engine on any subreddit they moderate.

### **Prerequisites**

* Docker and Docker Compose  
* Node.js (v20+)  
* A Reddit Account (with moderator access to a test subreddit)  
* A Google Gemini API Key  
* A Cloudflare account (or Ngrok) for secure local tunneling

### **Step 1: Deploy the Intelligence Backend**

The backend runs entirely inside Docker.

1. Navigate to the backend directory:  
   Bash  
   cd intelligence-backend

2. Configure environment variables:  
   Bash  
   cp .env.example .env

   *Add your GOOGLE\_API\_KEY and invent a strong DEVVIT\_WEBHOOK\_SECRET.*  
3. Build and launch the 4-container stack:  
   Bash  
   docker compose up \--build \-d

### **Step 2: Establish the Secure HTTPS Tunnel**

Reddit's Devvit platform strictly requires https:// webhooks. To route traffic to your local Docker backend (localhost:8000), you must use a secure tunnel.

* **Using Cloudflare Tunnels (Recommended for static domains):**  
  Route a subdomain (e.g., webhook.yourdomain.com) to http://localhost:8000.  
* **Using Ngrok (For temporary testing):**  
  Bash  
  ngrok http 8000

### **Step 3: Configure and Install the Devvit Sensor**

1. Navigate to the Devvit app directory:  
   Bash  
   cd ../scalable-social  
   npm install

2. Log into the Devvit CLI:  
   Bash  
   npx devvit login

3. Update the WEBHOOK\_URL constant inside src/main.tsx to point to your secure tunnel:  
   TypeScript  
   const WEBHOOK\_URL \= 'https://\<YOUR\_TUNNEL\_DOMAIN\>/api/v1/webhooks/devvit';

4. Upload and install the app to your test subreddit:  
   Bash  
   npx devvit playtest r/YourTestSubreddit

5. **Crucial Security Step:** Supply your Devvit app with the webhook secret you defined in your backend .env file so it passes the HMAC check:  
   Bash  
   npx devvit settings set webhookSecret "YOUR\_SECRET\_HERE"

## ---

**🛡 Compliance & Privacy**

This application is built defensively to comply with the Reddit Developer Terms and standard user privacy expectations:

* **No Commercial Profiling:** The engine is strictly configured as an academic trend analyzer. It does not profile users or facilitate direct commercial exploitation.  
* **Zero Raw Data Retention:** The PostgreSQL schema explicitly lacks the capacity to store verbatim post bodies or usernames.  
* **Approved LLMs:** Utilizes Google Gemini, an explicitly whitelisted inference engine per Reddit's Generative AI rules.  
* **Policies:** See the included [PRIVACY\_POLICY.md](https://www.google.com/search?q=PRIVACY_POLICY.md) and [TERMS\_OF\_SERVICE.md](https://www.google.com/search?q=TERMS_OF_SERVICE.md).

---

*Disclaimer: This project is an independent open-source proof of concept. It is not affiliated with, endorsed by, or sponsored by Reddit, Inc.*
