# **Scalable Social Data Aggregator**

**An asynchronous, webhook-driven data pipeline bridging serverless TypeScript applications with an isolated Python/Flask intelligence backend.**

## **🤖 Architect's Note: The AI-Assisted Build**

This repository is a proof-of-work demonstrating advanced **Agentic Orchestration** and **LLM-Assisted Development**. Designed, debugged, and deployed over an intensive 11-hour sprint, this project was built by actively directing multiple AI models to write, test, and integrate full-stack code. It highlights practical skills in systems architecture, prompt engineering, troubleshooting complex platform sandboxes (Reddit's Devvit), and deploying asynchronous machine learning pipelines.

## ---

**🏗 Architecture Overview**

This monorepo is divided into two decoupled environments: the serverless data extraction edge, and the stateful asynchronous intelligence engine.

Plaintext

┌───────────────────────────────────────────────────────────────────────┐  
│                           MONOREPO ROOT                               │  
├───────────────────────────┬───────────────────────────────────────────┤  
│  /scalable-social/        │  /intelligence-backend/                   │  
│  (Devvit Sensor App)      │  (Python/Flask \+ Celery \+ PostgreSQL)     │  
│                           │                                           │  
│  TypeScript \+ React       │  backend/                                 │  
│  webview dashboard        │    app/api.py        ← HMAC Webhook Auth  │  
│                           │    app/analysis\_tasks.py ← Gemini 2.5     │  
│  Daily scheduler job      │    app/models.py     ← PostgreSQL ORM     │  
│  scans posts, filters     │  docker-compose.yml                       │  
│  by intent regex,         │                                           │  
│  updates Redis metrics,   │  4-Container Stack:                       │  
│  and fires HTTP webhook.  │  Flask API, Celery Worker, Redis, DB      │  
└───────────────────────────┴───────────────────────────────────────────┘

### **🛠 The Tech Stack & Engineering Highlights**

This stack was chosen for strict data minimization, rapid horizontal scaling, and secure webhook handling.

* **Backend & API:** Python 3.12, Flask, SQLAlchemy (PostgreSQL), RESTful API Design.  
* **Asynchronous Queues:** Celery workers backed by Redis for durable message brokering.  
* **Frontend & Serverless:** Node.js, TypeScript, React, Reddit Devvit SDK.  
* **LLM Integration:** Google Gemini 2.5 Flash Lite SDK (Inference only, zero training).  
* **Infrastructure:** Docker Compose, Cloudflare Tunnels (Ingress), Constant-time HMAC SHA-256 Security.

### **🌊 The Webhook Lifecycle (Data Flow)**

1. **Extraction (Serverless Edge):** A Devvit scheduled job executes daily, fetching the last 24 hours of subreddit posts. It applies a regex intent-filter to isolate specific trend themes.  
2. **Transmission (Secure Tunnel):** Matched posts are batched into a JSON array and transmitted via an HTTPS POST webhook routed through a Cloudflare Tunnel. The payload is secured using a dynamic Authorization header.  
3. **Ingestion (Stateless API):** The Flask API receives the payload, verifies the HMAC signature, and instantly returns a 202 Accepted to bypass serverless execution timeouts. The batch is offloaded to Redis.  
4. **Analysis (Async Worker):** A persistent Celery worker picks up the batch and executes inference via the google-genai SDK to generate categorical research summaries, competitor analysis, and structured SWOT matrices.  
5. **Data Minimization:** Derived intelligence is persisted to PostgreSQL. **Raw text is permanently discarded in-memory and never stored.**  
6. **Real-Time UI:** The Reddit-native React webview fetches the processed intelligence to display a clean, executive-level dashboard.

## ---

**🚀 Open-Source Deployment Guide**

Developers can fork this repository to run their own asynchronous AI pipeline on any subreddit they moderate.

### **Prerequisites**

* Docker and Docker Compose  
* Node.js (v20+)  
* A Reddit Account (with moderator access to a test subreddit)  
* A Google Gemini API Key  
* A Cloudflare account (cloudflared daemon) for secure local tunneling

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

4. **Crucial Setup \- Initialize the Database:** Run the database migrations to build the PostgreSQL schema:  
   Bash  
   docker exec \-it intelligence-backend-web-1 flask db upgrade

### **Step 2: Establish the Secure HTTPS Tunnel**

Reddit's Devvit platform strictly requires https:// webhooks. To route traffic to your local Docker backend (localhost:8000), you must use a secure tunnel.

* Start your Cloudflare tunnel pointing to http://localhost:8000.  
* Verify it is alive:  
  Bash  
  curl \-v \-X POST https://\<YOUR\_TUNNEL\_DOMAIN\>/api/v1/webhooks/devvit

  *(You should receive an HTTP 401 Unauthorized—this means the tunnel works and the API is correctly blocking unauthenticated traffic).*

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

5. **Secure the Webhook:** Supply your Devvit app with the webhook secret you defined in your backend .env file so it passes the HMAC check:  
   Bash  
   npx devvit settings set webhookSecret "YOUR\_SECRET\_HERE"

### **Step 4: Test the Pipeline**

Because the Devvit scheduler only runs once every 24 hours, you can bypass Reddit to test your Docker backend immediately by sending a simulated payload:

Bash

curl \-X POST https://\<YOUR\_TUNNEL\_DOMAIN\>/api/v1/webhooks/devvit \\  
     \-H "Authorization: Bearer YOUR\_SECRET\_HERE" \\  
     \-H "Content-Type: application/json" \\  
     \-d "\[{\\"title\\":\\"I wish there was an app for this\\",\\"body\\":\\"Testing the pipeline.\\",\\"subreddit\\":\\"scalable\_social\_dev\\"}\]"

Check your worker logs (docker logs intelligence-backend-worker-1). You will see Celery process the payload, contact Gemini, and save the intelligence to PostgreSQL.

## ---

**🛡 Compliance & Privacy**

This application is built defensively to comply with Reddit Developer Terms and standard user privacy expectations:

* **No Commercial Profiling:** The engine is configured as an academic trend analyzer. It does not profile individual users.  
* **Zero Raw Data Retention:** The PostgreSQL schema explicitly lacks the capacity to store verbatim post bodies or usernames. Duplicate posts are hashed and rejected at the database level.  
* **Approved LLMs:** Utilizes Google Gemini, an explicitly whitelisted inference engine per Reddit's Generative AI rules.  
* **Policies:** See the included [PRIVACY\_POLICY.md](https://www.google.com/search?q=PRIVACY_POLICY.md) and [TERMS\_OF\_SERVICE.md](https://www.google.com/search?q=TERMS_OF_SERVICE.md).

---

*Disclaimer: This project is an independent open-source proof of concept. It is not affiliated with, endorsed by, or sponsored by Reddit, Inc.*
