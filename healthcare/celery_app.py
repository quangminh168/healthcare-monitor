"""Backward-compat shim. The real Celery app lives in celery_worker.py at project root."""
from celery_worker import celery  # noqa: F401
