"""Celery application factory.

Usage:
    celery -A healthcare.celery_app.celery worker --loglevel=info
    celery -A healthcare.celery_app.celery beat --loglevel=info
"""
import os
from celery import Celery
from celery.schedules import crontab

celery = Celery(__name__)

celery.conf.update(
    broker_url=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1'),
    result_backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        'run-retention-daily': {
            'task': 'healthcare.tasks.run_retention_task',
            'schedule': crontab(hour=3, minute=0),
        },
    },
)


class ContextTask(celery.Task):
    """Base task that pushes Flask app context so tasks can use db, mail, etc."""

    def __call__(self, *args, **kwargs):
        from healthcare import create_app
        app = create_app()
        with app.app_context():
            return self.run(*args, **kwargs)


celery.Task = ContextTask
