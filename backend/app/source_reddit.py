from __future__ import annotations
import requests
import time
import praw
import logging
from flask import current_app
from celery_app import celery_app
from .extensions import socketio, redis_client

API_URL = "http://web:8000/api/v1/ideas"
SOURCE_NAME = "Reddit"
SUBREDDITS = ["SomebodyMakeThis", "AppIdeas", "SideProject"]
USER_AGENT = "script:VVS-Discovery-Agent:v1.2 (by /u/EmotionalGap3249)"
PROGRESS_CURRENT_KEY = "discovery_progress_current"
PROGRESS_TOTAL_KEY = "discovery_progress_total"

logger = logging.getLogger(__name__)

def get_reddit_instance() -> praw.Reddit | None:
    required_keys = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"]
    if not all(current_app.config.get(k) for k in required_keys):
        error_msg = "[Reddit ERROR] Reddit credentials not fully configured in application configuration."
        logger.error(error_msg)
        return None
    return praw.Reddit(
        client_id=current_app.config.get("REDDIT_CLIENT_ID"),
        client_secret=current_app.config.get("REDDIT_CLIENT_SECRET"),
        user_agent=USER_AGENT,
        username=current_app.config.get("REDDIT_USERNAME"),
        password=current_app.config.get("REDDIT_PASSWORD"),
        requestor_kwargs={"timeout": 60}
    )

@celery_app.task(name="sourcing.reddit")
def scrape_reddit_task() -> str:
    reddit = get_reddit_instance()
    if not reddit:
        return "Reddit scraping failed due to configuration."

    ideas_found = 0
    logger.info("[Reddit] Sourcing task started.")
    
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
                    time.sleep(2) # Polite delay
            except praw.exceptions.APIException as e:
                logger.error(f"[Reddit API ERROR] Failed to scrape r/{subreddit_name} due to Reddit API: {e}")
                continue
            except requests.exceptions.RequestException as e:
                logger.error(f"[Reddit HTTP ERROR] Failed to scrape r/{subreddit_name} due to network issue: {e}")

    logger.info(f"[Reddit] Sourcing finished. Queued {ideas_found} ideas.")
    return f"Completed Reddit sourcing. Submitted {ideas_found} new ideas."