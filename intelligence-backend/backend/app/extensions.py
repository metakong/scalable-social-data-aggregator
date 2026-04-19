from __future__ import annotations
import os
import redis
from typing import Any
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_socketio import SocketIO

db: SQLAlchemy = SQLAlchemy()
migrate: Migrate = Migrate()

redis_url: str = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
socketio: SocketIO = SocketIO(message_queue=redis_url, async_mode='threading')
redis_client: redis.Redis[Any] = redis.Redis.from_url(redis_url, decode_responses=True)