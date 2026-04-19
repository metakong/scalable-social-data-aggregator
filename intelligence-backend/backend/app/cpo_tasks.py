from __future__ import annotations
import os
import json
import logging
import re
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from celery_app import celery_app
from .extensions import db, socketio
from .models import AppIdea, IdeaStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Devvit Webhook Processor (entry-point task)
# ---------------------------------------------------------------------------
@celery_app.task(
    name='tasks.process_devvit_webhook',
    rate_limit='30/m',
    autoretry_for=(google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def process_devvit_webhook(payload: dict[str, Any]) -> int:
    """
    Receives a raw Reddit post payload from the Devvit sensor via the
    webhook endpoint.  Runs Gemini SWOT + sentiment analysis, persists the
    derived intelligence (NOT the raw text), and pushes a Socket.IO event
    to the live dashboard.

    Expected payload keys: title, body, subreddit.
    """
    title = payload.get('title', '')
    body = payload.get('body', '')
    subreddit = payload.get('subreddit', 'unknown')

    # Combine title + body as the analysis input
    analysis_text = f"{title}\n\n{body}".strip()
    if not analysis_text:
        logger.warning("Empty payload received from r/%s — skipping.", subreddit)
        return -1

    socketio.emit('log_message', {
        'data': f'[WEBHOOK] Processing post from r/{subreddit}: "{title[:60]}…"'
    })

    # ---- Gemini Analysis ----
    analysis_data = _run_gemini_analysis(analysis_text, subreddit)

    # ---- Persist derived intelligence (raw text is NOT stored) ----
    idea = AppIdea(
        source_url=f"devvit://r/{subreddit}/{hash(analysis_text) & 0xFFFFFFFF:08x}",
        source_name=f"r/{subreddit}",
        # raw_text intentionally left NULL — we do not store raw Reddit text
        ai_generated_title=analysis_data.get("ai_generated_title"),
        ai_generated_summary=analysis_data.get("ai_generated_summary"),
        competition_analysis=analysis_data.get("competition_analysis"),
        swot_analysis=_build_swot_blob(analysis_data),
        status=IdeaStatus.PENDING_CEO_APPROVAL,
    )

    db.session.add(idea)
    db.session.commit()

    socketio.emit('log_message', {
        'data': f'[WEBHOOK] Intelligence saved as Idea {idea.id}. Ready for CEO review.'
    })
    socketio.emit('idea_update', {'idea': idea.to_dict()})

    return idea.id


# ---------------------------------------------------------------------------
# CPO Full Analysis (retained for manual/internal dispatches)
# ---------------------------------------------------------------------------
@celery_app.task(
    name='tasks.cpo_analysis',
    rate_limit='12/m',
    autoretry_for=(google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5
)
def cpo_analysis_task(idea_id: int) -> int:
    """
    Acts as the Chief Product Officer. Receives a vetted idea and generates
    the full product brief (Title, Description, SWOT, Opportunity Rating,
    Defeat Strategy) for CEO review.
    """
    idea = db.session.get(AppIdea, idea_id)
    if not idea:
        raise ValueError(f"Idea {idea_id} not found for CPO analysis.")

    socketio.emit('log_message', {'data': f'[CPO] Starting full analysis for Idea {idea.id}'})

    try:
        analysis_text = idea.raw_text or idea.ai_generated_summary or ''
        analysis_data = _run_gemini_analysis(analysis_text, idea.source_name, idea.competitor_data)

        idea.ai_generated_title = analysis_data.get("ai_generated_title")
        idea.ai_generated_summary = analysis_data.get("ai_generated_summary")
        idea.competition_analysis = analysis_data.get("competition_analysis")
        idea.swot_analysis = _build_swot_blob(analysis_data)
        idea.status = IdeaStatus.PENDING_CEO_APPROVAL
        db.session.commit()

        socketio.emit('log_message', {'data': f'[CPO] Full analysis complete for Idea {idea.id}. Ready for CEO review.'})
        socketio.emit('idea_update', {'idea': idea.to_dict()})

        return idea.id
    except (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable) as e:
        socketio.emit('log_message', {'data': f'[CPO WARNING] Rate limit hit for Idea {idea.id}. Retrying...'})
        raise e
    except Exception as e:
        socketio.emit('log_message', {'data': f'[CPO FATAL] Full analysis failed for Idea {idea.id}: {e}'})
        raise


# ---------------------------------------------------------------------------
# Shared Gemini helpers
# ---------------------------------------------------------------------------
def _run_gemini_analysis(
    text: str,
    source_label: str,
    competitor_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call Gemini 1.5 Flash and return the parsed JSON analysis dict."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    # Build optional competitor context
    competitor_context = "No competitor data available."
    if competitor_data and competitor_data.get("competitors"):
        competitors = competitor_data["competitors"]
        avg_rating = competitor_data.get("avg_rating", "N/A")
        lines = [f"Average competitor rating: {avg_rating}"]
        for name, info in competitors.items():
            rating = info.get("rating", "N/A")
            installs = info.get("installs", "N/A")
            lines.append(f"- {name}: rating={rating}, installs={installs}")
        competitor_context = "\n".join(lines)

    prompt = f"""
    You are the Chief Product Officer of a mobile app startup.
    For the following raw user idea sourced from {source_label},
    create a complete Product Brief.

    COMPETITOR LANDSCAPE:
    {competitor_context}

    Return ONLY a raw JSON object with six keys:
    1. "ai_generated_title": A concise, catchy, descriptive title.
    2. "ai_generated_summary": A detailed one-paragraph summary of the core
       problem and proposed solution.
    3. "competition_analysis": A brief one-paragraph analysis of the competitor
       landscape. Mention what a successful app needs to do to win.
    4. "swot_analysis": A JSON object with four keys ("strengths", "weaknesses",
       "opportunities", "threats"), each containing a bulleted list of 2-3 points.
    5. "opportunity_rating": An integer 1-10 rating the market opportunity.
       10 = wide open market, 1 = saturated with strong apps.
    6. "defeat_strategy": A specific paragraph describing UX/feature tactics
       to beat the listed weak competing apps.

    RAW IDEA TEXT: ---{text}---
    """

    response = model.generate_content(prompt)

    # Robust JSON extraction: strip markdown fences and conversational text
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not extract JSON from Gemini response: {response.text[:200]}")

    return json.loads(match.group())


def _build_swot_blob(analysis_data: dict[str, Any]) -> dict[str, Any]:
    """Merge opportunity_rating and defeat_strategy into the swot dict."""
    swot = analysis_data.get("swot_analysis", {})
    swot["opportunity_rating"] = analysis_data.get("opportunity_rating")
    swot["defeat_strategy"] = analysis_data.get("defeat_strategy")
    return swot