from app import create_app
from celery_app import celery_app

# Create a Flask app instance for the Celery worker
flask_app = create_app()

# Update the Celery app's configuration from the Flask app's config
celery_app.conf.update(flask_app.config)

# Add a context-aware Task base class
class ContextTask(celery_app.Task):
    def __call__(self, *args, **kwargs):
        with flask_app.app_context():
            # This line is now corrected to properly call the task's run method
            return self.run(*args, **kwargs)

celery_app.Task = ContextTask