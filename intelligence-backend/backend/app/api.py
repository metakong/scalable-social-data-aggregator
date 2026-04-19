from __future__ import annotations
import logging
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
# Devvit Webhook Receiver
# ---------------------------------------------------------------------------
@api_bp.route('/webhooks/devvit', methods=['POST'])
def devvit_webhook() -> tuple[Response, int]:
    """
    Receives real-time post data from the Devvit sensor app.
    Returns 202 immediately to prevent Devvit fetch() timeout drops,
    then dispatches the payload asynchronously to a Celery worker.
    """
    payload: dict | None = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid or missing JSON payload."}), 400

    required_fields = ('title', 'body', 'subreddit')
    if not all(field in payload for field in required_fields):
        return jsonify({
            "error": f"Missing required fields. Expected: {', '.join(required_fields)}"
        }), 400

    # Fire-and-forget: dispatch to Celery for async processing
    celery_app.send_task(
        'tasks.process_devvit_webhook',
        args=[payload],
    )

    logger.info(
        "Devvit webhook accepted from r/%s: %s",
        payload.get('subreddit', 'unknown'),
        payload.get('title', '')[:80],
    )

    return jsonify({"status": "accepted"}), 202


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