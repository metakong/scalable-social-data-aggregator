from celery import Celery
import os

celery_app = Celery("tasks",
                    broker=os.environ.get('CELERY_BROKER_URL'),
                    backend=os.environ.get('CELERY_RESULT_BACKEND_URL'),
                    include=[
                        'app.cso_tasks',
                        'app.cpo_tasks',
                        'app.source_mumsnet',
                        'app.source_reddit',
                        'app.source_hacker_news'
                    ])