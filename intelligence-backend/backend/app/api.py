from __future__ import annotations
import logging
import os
from typing import Any
from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from celery_app import celery_app
from .extensions import db, socketio, redis_client
from .models import AppIdea

api_bp = Blueprint('api', __name__)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Devvit Webhook Receiver (batched)
# ---------------------------------------------------------------------------
@api_bp.route('/webhooks/devvit', methods=['POST'])
def devvit_webhook() -> tuple[Response, int]:
    """
    Receives batched post data from the Devvit scheduler app.

    Accepts a JSON array of post objects, each containing:
      - title (str)
      - body (str)
      - subreddit (str)

    Returns 202 Accepted immediately, then dispatches the entire
    batch to a Celery worker for asynchronous Gemini analysis.
    """
    auth_header = request.headers.get('Authorization')
    expected_token = f"Bearer {os.getenv('DEVVIT_WEBHOOK_SECRET')}"
    if auth_header != expected_token:
        return jsonify({"error": "Unauthorized"}), 401

    payload: list | dict | None = request.get_json(silent=True)

    # Accept both a JSON array (batch) and a single object (wrapped into a list)
    if isinstance(payload, dict):
        payload = [payload]

    if not isinstance(payload, list) or len(payload) == 0:
        return jsonify({
            "error": "Invalid payload. Expected a non-empty JSON array of post objects."
        }), 400

    if len(payload) > 50:
        return jsonify({
            "error": "Batch size exceeds the maximum limit of 50 items."
        }), 400

    # Validate every item in the batch
    required_fields = ('title', 'body', 'subreddit')
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            return jsonify({
                "error": f"Item at index {idx} is not a JSON object."
            }), 400
        missing = [f for f in required_fields if f not in item]
        if missing:
            return jsonify({
                "error": f"Item at index {idx} missing required fields: {', '.join(missing)}"
            }), 400

    # Fire-and-forget: dispatch the full batch to Celery
    celery_app.send_task(
        'tasks.process_devvit_webhook_batch',
        args=[payload],
    )

    logger.info(
        "Devvit webhook batch accepted: %d posts from r/%s",
        len(payload),
        payload[0].get('subreddit', 'unknown') if payload else 'unknown',
    )

    return jsonify({
        "status": "accepted",
        "batch_size": len(payload),
    }), 202


# ---------------------------------------------------------------------------
# Ideas REST API (read-only dashboard feed)
# ---------------------------------------------------------------------------
@api_bp.route('/ideas', methods=['GET'])
def list_ideas() -> Response:
    """Returns all processed ideas, newest first."""
    db_session: Session = db.session
    ideas = db_session.execute(
        select(AppIdea).order_by(desc(AppIdea.created_at))
    ).scalars().all()
    ideas_list = [idea.to_dict() for idea in ideas]
    return jsonify(ideas_list)


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------
@api_bp.route('/status', methods=['GET'])
def get_dependency_status() -> Response:
    db_status = 'ok'
    redis_status = 'ok'
    try:
        db.session.execute(db.text('SELECT 1'))
    except Exception:
        db_status = 'error'
    try:
        redis_client.ping()
    except Exception:
        redis_status = 'error'
    return jsonify({
        "database_status": db_status,
        "redis_status": redis_status,
        "api_status": "online"
    })