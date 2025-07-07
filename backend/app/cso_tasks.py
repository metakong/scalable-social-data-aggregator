from __future__ import annotations
import time
import random
import logging
from celery_app import celery_app
from .extensions import db, socketio
from .models import AppIdea, IdeaStatus

logger = logging.getLogger(__name__)

def _check_competition(idea_text: str) -> bool:
    """Simulates checking Google Play Store competition. Returns True if competition is low."""
    # In a real scenario, this would involve scraping or API calls to the Play Store.
    # We simulate a 10% chance of an idea having low competition.
    low_competition = random.random() < 0.1
    logger.info(f"Simulated competition check for: '{idea_text[:50]}...' - Low competition: {low_competition}")
    return low_competition

@celery_app.task(name='tasks.cso_vetting')
def cso_vetting_task(idea_id: int) -> str:
    """
    Acts as the Chief Strategy Officer. Receives a new idea, checks for market
    competition, and either rejects it or passes it to the CPO for analysis.
    """
    try:
        idea = db.session.get(AppIdea, idea_id)
        if not idea:
            raise ValueError(f"Idea {idea_id} not found.")

        socketio.emit('log_message', {'data': f'[CSO] Vetting Idea {idea.id} for market competition.'})
        logger.info(f"Starting vetting for idea {idea.id}: '{idea.raw_text[:50]}...'")
        time.sleep(1) # Simulate work

        if _check_competition(idea.raw_text):
            socketio.emit('log_message', {'data': f'[CSO] Low competition found for Idea {idea.id}. Passing to CPO.'})
            logger.info(f"Idea {idea.id} passed vetting.")
            idea.status = IdeaStatus.PENDING_CPO_ANALYSIS
            db.session.commit()
            # Chain this task to the CPO task with a small delay
            celery_app.send_task('tasks.cpo_analysis', args=[idea.id], countdown=3)
            return f"Idea {idea.id} passed vetting. Sent to CPO."
        else:
            socketio.emit('log_message', {'data': f'[CSO] High competition found for Idea {idea.id}. Rejecting.'})
            logger.info(f"Idea {idea.id} rejected due to high competition.")
            idea.status = IdeaStatus.REJECTED_BY_CEO  # Consistent rejection status
            db.session.commit()
            return f"Idea {idea.id} rejected due to high market competition."

    except ValueError as e:
        error_message = f"[CSO ERROR] {e}"
        socketio.emit('log_message', {'data': error_message})
        logger.error(error_message)
        return f"CSO vetting task failed: {e}"
    except Exception as e:
        db.session.rollback()
        error_message = f"[CSO FATAL] An unexpected error occurred during vetting: {e}"
        socketio.emit('log_message', {'data': error_message})
        logger.exception(error_message) # Use logger.exception to include traceback
        raise  # Re-raise the exception to signal task failure to Celery