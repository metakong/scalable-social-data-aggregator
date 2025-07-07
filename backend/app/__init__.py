from __future__ import annotations
import logging
from flask import Flask
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
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    from .main import main_bp
    app.register_blueprint(main_bp)

    # Configure logging
    _configure_logging(app)

    return app

def _configure_logging(app: Flask) -> None:
    """Configures logging for the application."""
    log_level = logging.DEBUG if app.debug else logging.INFO

    # Create a file handler
    file_handler = logging.FileHandler('app.log')
    file_handler.setLevel(logging.WARNING)  # Log WARNING and above to file
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # Create a console handlert
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)  # Log INFO and above to console (or DEBUG in debug mode)
    console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)

    # Add handlers to the Flask app's logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)