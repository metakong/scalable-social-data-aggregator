from celery import Celery
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
                        'app.source_hacker_news'
                    ])