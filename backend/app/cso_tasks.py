from __future__ import annotations
import re
from google_play_scraper import search as play_search
from celery_app import celery_app
from .extensions import db, socketio
from .models import AppIdea, IdeaStatus

# Common stopwords to filter out when extracting search keywords
_STOPWORDS = frozenset({
    'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'it', 'they',
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'shall', 'can', 'need', 'must', 'dare',
    'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
    'into', 'about', 'between', 'through', 'after', 'before', 'above',
    'and', 'but', 'or', 'nor', 'not', 'so', 'if', 'than', 'that', 'this',
    'there', 'what', 'which', 'who', 'whom', 'when', 'where', 'why', 'how',
    'all', 'each', 'every', 'both', 'few', 'more', 'most', 'some', 'any',
    'just', 'very', 'really', 'like', 'wish', 'want', 'app', 'someone',
    'something', 'thing', 'would', 'make', 'build', 'get', 'use', 'tool',
})


def _extract_keywords(text: str, max_keywords: int = 4) -> str:
    """Extract the most significant words from raw text for Play Store search."""
    words = re.findall(r'[a-zA-Z]+', text.lower())
    keywords = [w for w in words if w not in _STOPWORDS and len(w) > 2]
    return ' '.join(keywords[:max_keywords])


@celery_app.task(name='tasks.cso_vetting')
def cso_vetting_task(idea_id: int) -> str:
    """
    Acts as the Chief Strategy Officer. Receives a new idea, performs a live
    Play Store search for competition, and either discards it or passes it
    to the CPO for analysis.
    """
    idea = db.session.get(AppIdea, idea_id)
    if not idea:
        return f"Idea {idea_id} not found."

    socketio.emit('log_message', {'data': f'[CSO] Vetting Idea {idea.id} for market competition.'})

    query = _extract_keywords(idea.raw_text or '')
    if not query:
        socketio.emit('log_message', {'data': f'[CSO] Could not extract keywords from Idea {idea.id}. Rejecting.'})
        db.session.delete(idea)
        db.session.commit()
        return f"Idea {idea.id} rejected: no searchable keywords."

    try:
        results = play_search(query, lang='en', country='us', n_hits=5)
    except Exception as e:
        socketio.emit('log_message', {'data': f'[CSO WARNING] Play Store search failed for Idea {idea.id}: {e}. Passing to CPO as fallback.'})
        # On search failure, pass the idea through rather than silently dropping it
        idea.status = IdeaStatus.PENDING_CPO_ANALYSIS
        db.session.commit()
        celery_app.send_task('tasks.cpo_analysis', args=[idea.id])
        return f"Idea {idea.id} passed vetting (search fallback). Sent to CPO."

    # Pass/Fail Logic:
    # Pass if 0 results, OR if top 5 apps have average rating strictly below 3.0
    if len(results) == 0:
        socketio.emit('log_message', {'data': f'[CSO] No competition found for Idea {idea.id}. Passing to CPO.'})
        idea.competitor_data = {"query": query, "competitors": {}}
        idea.status = IdeaStatus.PENDING_CPO_ANALYSIS
        db.session.commit()
        celery_app.send_task('tasks.cpo_analysis', args=[idea.id])
        return f"Idea {idea.id} passed vetting (no competition). Sent to CPO."

    # Build competitor data dict and compute average rating
    competitors = {}
    total_rating = 0.0
    rated_count = 0
    for app in results[:5]:
        app_name = app.get('title', 'Unknown')
        app_rating = app.get('score', 0.0) or 0.0
        competitors[app_name] = {
            "rating": app_rating,
            "appId": app.get('appId', ''),
            "installs": app.get('installs', 'N/A'),
        }
        total_rating += app_rating
        rated_count += 1

    avg_rating = total_rating / rated_count if rated_count > 0 else 0.0

    if avg_rating < 3.0:
        socketio.emit('log_message', {
            'data': f'[CSO] Weak competition found for Idea {idea.id} (avg rating: {avg_rating:.1f}). Passing to CPO.'
        })
        idea.competitor_data = {"query": query, "avg_rating": avg_rating, "competitors": competitors}
        idea.status = IdeaStatus.PENDING_CPO_ANALYSIS
        db.session.commit()
        celery_app.send_task('tasks.cpo_analysis', args=[idea.id])
        return f"Idea {idea.id} passed vetting (weak competition, avg={avg_rating:.1f}). Sent to CPO."
    else:
        socketio.emit('log_message', {
            'data': f'[CSO] Strong competition found for Idea {idea.id} (avg rating: {avg_rating:.1f}). Rejecting.'
        })
        db.session.delete(idea)
        db.session.commit()
        return f"Idea {idea.id} rejected due to strong market competition (avg={avg_rating:.1f})."