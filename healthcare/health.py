import os
import logging
from flask import Blueprint, jsonify
from healthcare import db

logger = logging.getLogger(__name__)
health_bp = Blueprint('health', __name__)


def _check_redis():
    """Ping Redis. Returns 'connected' or error string."""
    try:
        import redis as redis_lib
        url = os.environ.get('CELERY_BROKER_URL', os.environ.get('RATELIMIT_STORAGE_URI', 'redis://localhost:6379/0'))
        r = redis_lib.from_url(url, socket_connect_timeout=2)
        r.ping()
        return 'connected'
    except Exception as e:
        logger.warning("Redis health check failed: %s", e)
        return str(e)


def _check_celery():
    """Ping Celery workers. Returns 'connected' or error string."""
    try:
        from celery_worker import celery
        inspector = celery.control.inspect(timeout=2)
        active = inspector.active()
        if active:
            return f'connected ({len(active)} workers)'
        return 'no active workers'
    except Exception as e:
        logger.warning("Celery health check failed: %s", e)
        return str(e)


@health_bp.route('/health')
def health():
    checks = {}
    status_code = 200

    try:
        db.session.execute(db.text('SELECT 1'))
        checks['database'] = 'connected'
    except Exception as e:
        checks['database'] = str(e)
        status_code = 503

    checks['redis'] = _check_redis()
    checks['celery'] = _check_celery()

    overall = 'healthy' if status_code == 200 else 'unhealthy'
    return jsonify({'status': overall, **checks}), status_code
