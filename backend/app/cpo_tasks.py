from __future__ import annotations
import os
import json
import re
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from celery_app import celery_app
from .extensions import db, socketio
from .models import AppIdea, IdeaStatus

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
    the full product brief (Title, Description, SWOT, Opportunity Rating,
    Defeat Strategy) for CEO review.
    """
    idea = db.session.get(AppIdea, idea_id)
    if not idea:
        raise ValueError(f"Idea {idea_id} not found for CPO analysis.")

    socketio.emit('log_message', {'data': f'[CPO] Starting full analysis for Idea {idea.id}'})

    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Build competitor context for the prompt
        competitor_context = "No competitor data available (idea passed with no competition found)."
        if idea.competitor_data and idea.competitor_data.get("competitors"):
            competitors = idea.competitor_data["competitors"]
            avg_rating = idea.competitor_data.get("avg_rating", "N/A")
            lines = [f"Average competitor rating: {avg_rating}"]
            for name, info in competitors.items():
                rating = info.get("rating", "N/A")
                installs = info.get("installs", "N/A")
                lines.append(f"- {name}: rating={rating}, installs={installs}")
            competitor_context = "\n".join(lines)

        prompt = f"""
        You are the Chief Product Officer of a mobile app startup.
        For the following raw user idea, your task is to create a complete Product Brief.

        COMPETITOR LANDSCAPE (from Play Store search):
        {competitor_context}

        Return ONLY a raw JSON object with six keys:
        1. "ai_generated_title": A concise, catchy, and descriptive title.
        2. "ai_generated_summary": A detailed one-paragraph summary of the core problem and solution.
        3. "competition_analysis": A brief, one-paragraph analysis of the competitor landscape based on the data above. Mention what a successful app in this space needs to do to win.
        4. "swot_analysis": A JSON object with four keys ("strengths", "weaknesses", "opportunities", "threats"), each containing a bulleted list of 2-3 points.
        5. "opportunity_rating": An integer score from 1-10 rating the market opportunity based on competitor weakness. 10 = wide open market, 1 = saturated with strong apps.
        6. "defeat_strategy": A specific paragraph describing UX/feature tactics to beat the listed weak competing apps. Be concrete and actionable.

        RAW IDEA TEXT: ---{idea.raw_text}---
        """
        response = model.generate_content(prompt)

        # Robust JSON extraction: strip markdown fences and conversational text
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if not match:
            raise ValueError(f"Could not extract JSON from Gemini response: {response.text[:200]}")
        analysis_data = json.loads(match.group())

        idea.ai_generated_title = analysis_data.get("ai_generated_title")
        idea.ai_generated_summary = analysis_data.get("ai_generated_summary")
        idea.competition_analysis = analysis_data.get("competition_analysis")

        # Embed opportunity_rating and defeat_strategy into swot_analysis JSONB
        swot = analysis_data.get("swot_analysis", {})
        swot["opportunity_rating"] = analysis_data.get("opportunity_rating")
        swot["defeat_strategy"] = analysis_data.get("defeat_strategy")
        idea.swot_analysis = swot

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