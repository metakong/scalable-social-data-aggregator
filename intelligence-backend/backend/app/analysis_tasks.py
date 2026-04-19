from __future__ import annotations
import os
import json
import logging
import re
from typing import Any

from google import genai
from google.api_core import exceptions as google_exceptions

from celery_app import celery_app
from .extensions import db, socketio
from .models import AppIdea, IdeaStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Devvit Webhook Batch Processor (entry-point task)
# ---------------------------------------------------------------------------
@celery_app.task(
    name='tasks.process_devvit_webhook_batch',
    rate_limit='10/m',
    autoretry_for=(google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def process_devvit_webhook_batch(batch: list[dict[str, Any]]) -> list[int]:
    """
    Processes a batched array of Reddit post payloads from the Devvit
    scheduler webhook.  Each item is analysed individually via Gemini,
    persisted as derived intelligence, and pushed to the live dashboard.

    Raw Reddit text is NEVER stored in the database.
    """
    created_ids: list[int] = []

    socketio.emit('log_message', {
        'data': f'[WEBHOOK] Processing batch of {len(batch)} posts…'
    })

    for idx, payload in enumerate(batch):
        title = payload.get('title', '')
        body = payload.get('body', '')
        subreddit = payload.get('subreddit', 'unknown')

        analysis_text = f"{title}\n\n{body}".strip()
        if not analysis_text:
            logger.warning("Empty payload at batch index %d from r/%s — skipping.", idx, subreddit)
            continue

        socketio.emit('log_message', {
            'data': f'[WEBHOOK] [{idx + 1}/{len(batch)}] Analysing post from r/{subreddit}: "{title[:60]}…"'
        })

        try:
            # ---- Gemini Analysis ----
            analysis_data = _run_gemini_analysis(analysis_text, subreddit)

            # ---- Persist derived intelligence (raw text is NOT stored) ----
            idea = AppIdea(
                source_url=f"devvit://r/{subreddit}/{hash(analysis_text) & 0xFFFFFFFF:08x}",
                source_name=f"r/{subreddit}",
                ai_generated_title=analysis_data.get("ai_generated_title"),
                ai_generated_summary=analysis_data.get("ai_generated_summary"),
                competition_analysis=analysis_data.get("competition_analysis"),
                swot_analysis=_build_swot_blob(analysis_data),
                status=IdeaStatus.ANALYSIS_COMPLETE,
            )
            db.session.add(idea)
            db.session.commit()

            socketio.emit('idea_update', {'idea': idea.to_dict()})
            created_ids.append(idea.id)

        except Exception as e:
            db.session.rollback()
            logger.error("Failed to process batch item %d from r/%s: %s", idx, subreddit, e)
            socketio.emit('log_message', {
                'data': f'[WEBHOOK] Failed to process item {idx + 1}: {e}'
            })

    socketio.emit('log_message', {
        'data': f'[WEBHOOK] Batch complete. {len(created_ids)}/{len(batch)} ideas created.'
    })

    return created_ids


# ---------------------------------------------------------------------------
# Full Analysis (retained for manual/internal dispatches)
# ---------------------------------------------------------------------------
@celery_app.task(
    name='tasks.analysis_task',
    rate_limit='12/m',
    autoretry_for=(google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5
)
def analysis_task(idea_id: int) -> int:
    """
    Acts as the Academic Trend Analyzer. Receives a vetted idea and generates
    the Open Source Research Summary.
    """
    idea = db.session.get(AppIdea, idea_id)
    if not idea:
        raise ValueError(f"Idea {idea_id} not found for analysis.")

    socketio.emit('log_message', {'data': f'[ANALYZER] Starting full analysis for Idea {idea.id}'})

    try:
        # Since raw_text is removed, we only run on ai_generated_summary if available
        analysis_text = idea.ai_generated_summary or ''
        analysis_data = _run_gemini_analysis(analysis_text, idea.source_name)

        idea.ai_generated_title = analysis_data.get("ai_generated_title")
        idea.ai_generated_summary = analysis_data.get("ai_generated_summary")
        idea.competition_analysis = analysis_data.get("competition_analysis")
        idea.swot_analysis = _build_swot_blob(analysis_data)
        idea.status = IdeaStatus.ANALYSIS_COMPLETE
        db.session.commit()

        socketio.emit('log_message', {'data': f'[ANALYZER] Full analysis complete for Idea {idea.id}. Ready for review.'})
        socketio.emit('idea_update', {'idea': idea.to_dict()})

        return idea.id
    except (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable) as e:
        socketio.emit('log_message', {'data': f'[ANALYZER WARNING] Rate limit hit for Idea {idea.id}. Retrying...'})
        raise e
    except Exception as e:
        socketio.emit('log_message', {'data': f'[ANALYZER FATAL] Full analysis failed for Idea {idea.id}: {e}'})
        raise


# ---------------------------------------------------------------------------
# Shared Gemini helpers
# ---------------------------------------------------------------------------
def _run_gemini_analysis(
    text: str,
    source_label: str,
) -> dict[str, Any]:
    """Call Gemini 2.0 Flash and return the parsed JSON analysis dict."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
    You are an Academic Trend Analyzer researching digital community behaviors.
    For the following community discussion excerpt sourced from {source_label},
    create an Open Source Research Summary.

    Return ONLY a raw JSON object with four keys:
    1. "ai_generated_title": A concise, descriptive title for the research topic.
    2. "ai_generated_summary": A detailed one-paragraph summary of the core discussion and themes.
    3. "competition_analysis": A brief one-paragraph analysis of existing tools or academic literature addressing this theme.
    4. "swot_analysis": A JSON object with four keys ("strengths", "weaknesses",
       "opportunities", "threats"), each containing a bulleted list of 2-3 points related to researching this topic.

    RAW TEXT EXCERPT: ---{text}---
    """

    response = client.models.generate_content(
        model='gemini-2.5-flash-lite',
        contents=prompt,
    )

    # Robust JSON extraction: strip markdown fences and conversational text
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not extract JSON from Gemini response: {response.text[:200]}")

    return json.loads(match.group())


def _build_swot_blob(analysis_data: dict[str, Any]) -> dict[str, Any]:
    """Return the swot dict directly since we removed commercial ratings."""
    return analysis_data.get("swot_analysis", {})