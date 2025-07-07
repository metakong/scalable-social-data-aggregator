from __future__ import annotations
import os
import redis
from typing import Any
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_socketio import SocketIO

db: SQLAlchemy = SQLAlchemy()
migrate: Migrate = Migrate()
socketio: SocketIO = SocketIO()
