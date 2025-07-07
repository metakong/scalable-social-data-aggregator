from __future__ import annotations
from typing import Any
from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from celery_app import celery_app
from .extensions import db, socketio, redis_client
from .models import AppIdea, IdeaStatus

api_bp = Blueprint('api', __name__)

PROGRESS_CURRENT_KEY = "discovery_progress_current"
PROGRESS_TOTAL_KEY = "discovery_progress_total"

@api_bp.route('/sourcing/start', methods=['POST'])
def start_sourcing_task() -> Response:
    try:
        r = redis_client
        r.set(PROGRESS_CURRENT_KEY, 0)
        r.set(PROGRESS_TOTAL_KEY, 0)
        socketio.emit('progress_update', {'current': 0, 'total': 0})
        socketio.emit('log_message', {'data': 'Discovery cycle initiated...'})
    except Exception as e:
        current_app.logger.error(f"Could not reset Redis progress: {e}")

    # Dispatch all sourcing tasks
    celery_app.send_task('sourcing.mumsnet')
    celery_app.send_task('sourcing.reddit')
    celery_app.send_task('sourcing.hacker_news')

    return jsonify({"message": "All sourcing tasks initiated."})

@api_bp.route('/ideas', methods=['GET', 'POST'])
def handle_ideas() -> Response | tuple[Response, int]:
    db_session: Session = db.session
    if request.method == 'POST':
        data: dict | None = request.get_json()
        if not isinstance(data, dict) or not all(k in data for k in ['source_url', 'source_name', 'raw_text']):
            return jsonify({"error": "Missing required fields"}), 400

        if db_session.execute(select(AppIdea).filter_by(source_url=data['source_url'])).first():
            return jsonify({"error": f"An idea with source_url '{data['source_url']}' already exists."}), 409

        new_idea = AppIdea(
            source_url=data['source_url'],
            source_name=data['source_name'],
            raw_text=data['raw_text']
            # Status now defaults to PENDING_CSO_VETTING
        )
        db_session.add(new_idea)
        db_session.commit()

        # The new idea is now sent to the CSO for vetting, not directly to an analyst.
        celery_app.send_task('tasks.cso_vetting', args=[new_idea.id])

        return jsonify({
            "message": "AppIdea created and dispatched for CSO vetting",
            "idea": {"id": new_idea.id, "status": new_idea.status.value}
        }), 201

    # GET request
    ideas = db_session.execute(select(AppIdea).order_by(desc(AppIdea.created_at))).scalars().all()
    # Use the new to_dict() method for serialization
    ideas_list = [idea.to_dict() for idea in ideas]
    return jsonify(ideas_list)


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

@api_bp.route('/ideas/<int:idea_id>/approve', methods=['POST'])
def approve_idea(idea_id: int) -> Response | tuple[Response, int]:
    """Approves an idea, saves feedback, and triggers the development kickoff."""
    db_session: Session = db.session
    idea = db_session.get(AppIdea, idea_id)
    if not idea:
        return jsonify({"error": "Idea not found"}), 404

    data = request.get_json() or {}
    feedback = data.get('ceo_feedback', '')

    idea.status = IdeaStatus.APPROVED_FOR_DEV
    idea.ceo_feedback = feedback
    db_session.commit()

    log_msg = f'[CEO] Idea {idea.id} approved for development. Kicking off CTO task.'
    socketio.emit('log_message', {'data': log_msg})
    socketio.emit('idea_update', {'idea': idea.to_dict()})

    # Dispatch the placeholder task for the CTO agent
    celery_app.send_task('tasks.cto_development_kickoff', args=[idea.id], countdown=5)  # Add a delay

    return jsonify({
        "message": f"Idea {idea_id} approved and sent for development.",
        "idea": idea.to_dict()
    })

@api_bp.route('/ideas/<int:idea_id>/reject', methods=['POST'])
def reject_idea(idea_id: int) -> Response | tuple[Response, int]:
    """Rejects an idea and saves the feedback."""
    db_session: Session = db.session
    idea = db_session.get(AppIdea, idea_id)
    if not idea:
        return jsonify({"error": "Idea not found"}), 404

    data = request.get_json() or {}
    feedback = data.get('ceo_feedback', '')

    idea.status = IdeaStatus.REJECTED_BY_CEO
    idea.ceo_feedback = feedback
    db_session.commit()

    log_msg = f'[CEO] Idea {idea.id} rejected. Feedback: "{feedback}"'
    socketio.emit('log_message', {'data': log_msg})
    socketio.emit('idea_update', {'idea': idea.to_dict()})

    return jsonify({
        "message": f"Idea {idea_id} has been rejected.",
        "idea": idea.to_dict()
    })
