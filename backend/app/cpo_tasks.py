from __future__ import annotations
import json
import time
import logging
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from flask import current_app
from celery_app import celery_app
from .extensions import db, socketio
from .models import AppIdea, IdeaStatus

logger = logging.getLogger(__name__)

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
    Acts as the Chief Product Officer. Receives a CSO-vetted idea and generates
    the full product brief (Title, Description, SWOT) for CEO review.
    """
    idea = db.session.get(AppIdea, idea_id)
    if not idea:
        raise ValueError(f"Idea {idea_id} not found for CPO analysis.")

    socketio.emit('log_message', {'data': f'[CPO] Starting analysis for Idea {idea.id}'})

    try:
        api_key = current_app.config.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in application configuration.")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = f"""
        You are the Chief Product Officer of a mobile app startup.
        For the following raw user idea, your task is to create a complete Product Brief.
        Return ONLY a raw JSON object with four keys:
        1. "ai_generated_title": A concise, catchy, and descriptive title.
        2. "ai_generated_summary": A detailed one-paragraph summary of the core problem and solution.
        3. "competition_analysis": A brief, one-paragraph analysis of the potential competition landscape, assuming it is low (as it has passed CSO vetting). Mention what a successful app in this space needs to do to win.
        4. "swot_analysis": A JSON object with four keys ("strengths", "weaknesses", "opportunities", "threats"), each containing a bulleted list of 2-3 points.

        RAW IDEA TEXT: ---{idea.raw_text}---
        """
        response = model.generate_content(prompt)
        time.sleep(1)
        cleaned_response_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        try:
            analysis_data = json.loads(cleaned_response_text)
        except json.JSONDecodeError as e:
            logger.error(f"[CPO] JSON decode error for Idea {idea.id}: {e}\nResponse text: {cleaned_response_text}")
            raise ValueError(f"Invalid JSON format from Gemini: {e}") from e

        if not all(k in analysis_data for k in ["ai_generated_title", "ai_generated_summary", "competition_analysis", "swot_analysis"]):
            logger.warning(f"[CPO] Incomplete data from Gemini for Idea {idea.id}: {analysis_data}")
            raise ValueError("Incomplete product brief data received from Gemini.")

        with db.session.begin_nested(): # Use a nested transaction for safety.
            idea.ai_generated_title = analysis_data.get("ai_generated_title")
            idea.ai_generated_summary = analysis_data.get("ai_generated_summary")
            idea.competition_analysis = analysis_data.get("competition_analysis")
            idea.swot_analysis = analysis_data.get("swot_analysis")
            idea.status = IdeaStatus.PENDING_CEO_APPROVAL
            db.session.add(idea)

        db.session.commit()  # Commit the outer transaction
        socketio.emit('log_message', {'data': f'[CPO] Analysis complete for Idea {idea.id}.'})
        socketio.emit('idea_update', {'idea': idea.to_dict()})  # Emit update after commit

        return idea.id
    except (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable) as e:
        socketio.emit('log_message', {'data': f'[CPO WARNING] Gemini API issue for Idea {idea.id}: {e}. Will retry.'})
        raise  # Re-raise for Celery retry
    except Exception as e:
        socketio.emit('log_message', {'data': f'[CPO FATAL] Analysis failed for Idea {idea.id}: {e}'})
        raise # Re-raise to signal task failure
