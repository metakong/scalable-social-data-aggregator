from __future__ import annotations
import os
import requests
import praw
from celery_app import celery_app
from .extensions import socketio, redis_client

API_URL = "http://web:8000/api/v1/ideas"
SOURCE_NAME = "Reddit"
SUBREDDITS = ["SomebodyMakeThis", "AppIdeas", "SideProject"]
USER_AGENT = "script:VVS-Discovery-Agent:v1.2 (by /u/EmotionalGap3249)"
PROGRESS_CURRENT_KEY = "discovery_progress_current"
PROGRESS_TOTAL_KEY = "discovery_progress_total"

def get_reddit_instance() -> praw.Reddit | None:
    if not all(k in os.environ for k in ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"]):
        socketio.emit('log_message', {'data': '[Reddit ERROR] Reddit credentials not fully configured in .env file.'})
        return None
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=USER_AGENT,
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        requestor_kwargs={"timeout": 60}
    )

@celery_app.task(name="sourcing.reddit")
def scrape_reddit_task() -> str:
    reddit = get_reddit_instance()
    if not reddit:
        return "Reddit scraping failed due to configuration."

    ideas_found = 0
    socketio.emit('log_message', {'data': '[Reddit] Sourcing task started.'})
    
    total_posts_to_scan = len(SUBREDDITS) * 10
    redis_client.incrby(PROGRESS_TOTAL_KEY, total_posts_to_scan)

    with requests.Session() as client:
        for subreddit_name in SUBREDDITS:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                for submission in subreddit.hot(limit=10):
                    redis_client.incr(PROGRESS_CURRENT_KEY)
                    if submission.stickied:
                        continue
                    
                    full_url = f"https://www.reddit.com{submission.permalink}"
                    post_response = client.post(
                        API_URL,
                        json={
                            "source_url": full_url,
                            "source_name": f"{SOURCE_NAME}::r/{subreddit_name}",
                            "raw_text": f"{submission.title}\n\n{submission.selftext}",
                        },
                        timeout=10.0,
                    )
                    if post_response.status_code == 201:
                        ideas_found += 1
            except Exception as e:
                socketio.emit('log_message', {'data': f"[Reddit ERROR] Failed to scrape r/{subreddit_name}: {e}"})

    socketio.emit('log_message', {'data': f'[Reddit] Sourcing finished. Queued {ideas_found} ideas.'})
    return f"Completed Reddit sourcing. Submitted {ideas_found} new ideas."