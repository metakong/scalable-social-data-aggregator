from __future__ import annotations
from flask import Flask
from config import Config
from .extensions import db, migrate, socketio

def create_app(config_class: type[Config] = Config) -> Flask:
    """
    Application factory. Celery is no longer configured here
    to break the circular dependency.
    """
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, message_queue=app.config['CELERY_BROKER_URL'])

    # Import and register blueprints
    from .api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from .main import main_bp
    app.register_blueprint(main_bp)

    return app