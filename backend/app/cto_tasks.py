from __future__ import annotations
import json
import time
import os
import subprocess
import logging
from pathlib import Path

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from flask import current_app

from celery_app import celery_app
from .extensions import db, socketio
from .models import AppIdea, IdeaStatus

logger = logging.getLogger(__name__)

def _generate_app_description(idea: AppIdea) -> str:
    """
    Generates a detailed app description suitable for a code generation prompt.
    """
    api_key = current_app.config.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in application configuration.")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')  # Or another suitable model

        # Define an improved prompt for Gemini to generate a complete Android project
        prompt = f"Generate an Android app based on the idea: {idea.ai_generated_summary}"

        response = model.generate_content(prompt, request_options={'timeout': 300})  # Increased timeout

        if not response.text:
            raise ValueError("Gemini returned an empty response.")

        return response.text  # Return the generated code as a string

    except (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable) as e:
        socketio.emit('log_message', {'data': f'[CTO WARNING] Gemini API error (rate limit or service issue): {e}'})
        raise  # Re-raise for Celery retry on transient errors
    except Exception as e:
        socketio.emit('log_message', {'data': f'[CTO FATAL] Code generation failed: {e}'})
        raise
    # Placeholder functionality - returns an empty string
    return ""
