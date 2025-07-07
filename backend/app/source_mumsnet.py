from __future__ import annotations
import json
import time
import httpx
import logging
from celery_app import celery_app
from playwright.sync_api import sync_playwright, Page, BrowserContext, Error
from flask import current_app
from .extensions import socketio, redis_client

API_URL = "http://web:8000/api/v1/ideas"
SOURCE_NAME = "Mumsnet"
TARGET_URL = "https://www.mumsnet.com/talk/am_i_being_unreasonable"
STATE_FILE = "/tmp/mumsnet_state.json"
PROGRESS_CURRENT_KEY = "discovery_progress_current"
PROGRESS_TOTAL_KEY = "discovery_progress_total"

logger = logging.getLogger(__name__)

def get_playwright_context() -> tuple[BrowserContext, callable] | tuple[None, None]:
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")
        def cleanup():
            context.close()
            browser.close()
            pw.stop()
        return context, cleanup
    except Error as e:
        logger.error(f"[Playwright ERROR] Failed to initialize: {e}")
        return None, None

def ensure_login(page: Page, context: BrowserContext) -> bool:
    username = current_app.config.get("MUMSNET_USERNAME")
    password = current_app.config.get("MUMSNET_PASSWORD")
    if not username or not password:
        socketio.emit('log_message', {'data': '[Mumsnet ERROR] Credentials not found in application configuration.'})
        raise ValueError("Mumsnet credentials not found.")
    try:
        with open(STATE_FILE, 'r') as f:
            storage_state = json.load(f)
        context.add_cookies(storage_state['cookies'])
        page.goto(TARGET_URL, timeout=30000) # Quick check to see if cookies are valid
        if "Log in" in page.content():
            raise FileNotFoundError("Session expired")
        socketio.emit('log_message', {'data': '[Mumsnet] Saved session state loaded.'})
        return True
    except (FileNotFoundError, Error):
        socketio.emit('log_message', {'data': '[Mumsnet] No valid session. Performing fresh login.'})
        page.goto("https://www.mumsnet.com/account/login", timeout=60000)
        page.fill('input[name="email"]', username)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_url("https://www.mumsnet.com/", timeout=60000, wait_until="domcontentloaded")
        storage = {"cookies": context.cookies()}
        with open(STATE_FILE, 'w') as f:
            json.dump(storage, f)
        logger.info('[Mumsnet] Login successful and session saved.')
        return True

@celery_app.task(name="sourcing.mumsnet")
def scrape_mumsnet() -> str:
    logger.info('[Mumsnet] Sourcing task started.')
    context, cleanup = get_playwright_context()
    if not context:
        return "Mumsnet sourcing failed: Could not start Playwright."
    
    page = context.new_page()
    try:
        if not ensure_login(page, context):
            raise Exception("Login failed or credentials not configured.")

        page.goto(TARGET_URL, timeout=60000)
        thread_elements = page.locator('div[data-thread-id]').all()
        if not thread_elements:
            raise Exception("No discussion threads found on page.")

        r = redis_client
        r.set(PROGRESS_TOTAL_KEY, len(thread_elements))
        ideas_found = 0

        for i, element in enumerate(thread_elements):
            r.set(PROGRESS_CURRENT_KEY, i + 1)
            socketio.emit('progress_update', {'current': i + 1, 'total': len(thread_elements)})
            try:
                title_element = element.locator('h2 a').first
                title = title_element.inner_text()
                url = title_element.get_attribute('href')
                full_url = f"https://www.mumsnet.com{url}" if not (url.startswith('http') or url.startswith('//')) else url
                
                with httpx.Client() as client:
                    response = client.post(
                        "http://web:8000/api/v1/ideas",
                        json={"source_url": full_url, "source_name": SOURCE_NAME, "raw_text": title},
                        timeout=10.0
                    )
                    if response.status_code == 201:
                        ideas_found += 1
                    time.sleep(2)  # Polite delay
            except Exception as e:
                socketio.emit('log_message', {'data': f'[Mumsnet ERROR] Could not process thread: {e}'})
        
        logger.info(f'[Mumsnet] Sourcing finished. Queued {ideas_found} ideas.')
        return f"Completed Mumsnet sourcing. Submitted {ideas_found} new ideas."
    except Exception as e:
        error_message = f'[Mumsnet FATAL] Sourcing failed: {e}'
        socketio.emit('log_message', {'data': error_message})
        return error_message
    finally:
        if cleanup:
            cleanup()