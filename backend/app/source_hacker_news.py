from __future__ import annotations
import requests
import time
from celery_app import celery_app
from flask import current_app
from .extensions import socketio, redis_client  # Assume you have a Redis client

API_URL = "http://web:8000/api/v1/ideas"
SOURCE_NAME = "Hacker News"
HN_API_BASE_URL = "https://hacker-news.firebaseio.com/v0"
PROGRESS_CURRENT_KEY = "discovery_progress_current"
PROGRESS_TOTAL_KEY = "discovery_progress_total"
POST_REQUEST_TIMEOUT = 15  # Increased timeout

def _fetch_item(session: requests.Session, item_id: int) -> dict | None:
    url = f"{HN_API_BASE_URL}/item/{item_id}.json"
    try:
        response = session.get(url, timeout=20.0)  # Increased timeout
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        socketio.emit('log_message', {'data': f'[HN ERROR] Failed to fetch item {item_id}: {e}'})
        return None

@celery_app.task(name="sourcing.hacker_news", time_limit=7200)  # Time limit of 2 hours
def scrape_hacker_news_task() -> str:
    socketio.emit('log_message', {'data': '[HN] Sourcing task started.'})
    ideas_found = 0
    with requests.Session() as session:
        try:
            top_stories_url = f"{HN_API_BASE_URL}/topstories.json"
            response = session.get(top_stories_url, timeout=30.0)  # Increased timeout
            response.raise_for_status()
            top_story_ids = response.json()[:60]  # Increased limit
            redis_client.incrby(PROGRESS_TOTAL_KEY, len(top_story_ids))
        except requests.RequestException as e:
            socketio.emit('log_message', {'data': f'[HN ERROR] Could not fetch top stories: {e}'})
            return "Failed to fetch top stories."

        for item_id in top_story_ids:
            redis_client.incr(PROGRESS_CURRENT_KEY)  # Increment current progress
            item = _fetch_item(session, item_id)
            if item and item.get("type") == "story" and item.get("url"):
                try:
                    post_response = session.post(  # Post to API with increased timeout
                        API_URL,
                        json={
                            "source_url": item["url"],
                            "source_name": SOURCE_NAME,
                            "raw_text": item.get("title", "No Title"),
                        },
                        timeout=10.0,

                    )
                    if post_response.status_code == 201:
                        ideas_found += 1
                except requests.RequestException as e:
                    socketio.emit('log_message', {'data': f"[HN ERROR] Could not post idea '{item.get('title')}': {e}"})
                time.sleep(3)  # Added a more polite delay
            else:
                time.sleep(1)  # Small delay for non-story items

    socketio.emit('log_message', {'data': f'[HN] Sourcing finished. Queued {ideas_found} ideas.'})
    return f"Completed Hacker News sourcing. Submitted {ideas_found} new ideas."