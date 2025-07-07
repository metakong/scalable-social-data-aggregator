from celery import Celery, signals
import os

celery_app = Celery("tasks",
                    broker=os.environ.get('CELERY_BROKER_URL'),
                    backend=os.environ.get('CELERY_RESULT_BACKEND_URL'),
                    include=[
                        # 'app.tasks', # Obsolete, replaced by specific agent tasks
                        'app.cso_tasks', # Chief Strategy Officer agent
                        'app.cpo_tasks', # Chief Product Officer agent
                        'app.source_mumsnet',
                        'app.source_reddit',  
                        'app.source_hacker_news',
                        'app.cto_tasks'         # Chief Technology Officer agent
                    ])

@signals.setup_logging.connect
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig
    from app import log_config  # Import your log configuration
    dictConfig(log_config)