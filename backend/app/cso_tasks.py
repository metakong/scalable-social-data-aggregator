from __future__ import annotations
import time
from celery_app import celery_app
from .extensions import db, socketio
from .models import AppIdea, IdeaStatus

# This is a placeholder for a future, more complex competition analysis.
# For now, we will simulate the 90% rejection rate.
def _check_competition(idea_text: str) -> bool:
    """Simulates checking Google Play Store competition. Returns True if competition is low."""
    # In a real scenario, this would involve scraping or API calls to the Play Store.
    # We simulate a 10% chance of an idea having low competition.
    import random
    return random.random() < 0.1

@celery_app.task(name='tasks.cso_vetting')
def cso_vetting_task(idea_id: int) -> str:
    """
    Acts as the Chief Strategy Officer. Receives a new idea, checks for market
    competition, and either discards it or passes it to the CPO for analysis.
    """
    idea = db.session.get(AppIdea, idea_id)
    if not idea:
        return f"Idea {idea_id} not found."

    socketio.emit('log_message', {'data': f'[CSO] Vetting Idea {idea.id} for market competition.'})
    time.sleep(1) # Simulate work

    if _check_competition(idea.raw_text):
        socketio.emit('log_message', {'data': f'[CSO] Low competition found for Idea {idea.id}. Passing to CPO.'})
        idea.status = IdeaStatus.PENDING_CPO_ANALYSIS
        db.session.commit()
        # Chain this task to the CPO task
        celery_app.send_task('tasks.cpo_analysis', args=[idea.id])
        return f"Idea {idea.id} passed vetting. Sent to CPO."
    else:
        socketio.emit('log_message', {'data': f'[CSO] High competition found for Idea {idea.id}. Rejecting.'})
        db.session.delete(idea) # Or set status to a new REJECTED_BY_CSO state
        db.session.commit()
        return f"Idea {idea.id} rejected due to high market competition."