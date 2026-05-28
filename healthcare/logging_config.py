"""Production logging configuration.

Provides:
- RotatingFileHandler (10 MB, 10 backups)
- JSON formatter for production
- Console formatter for development
- RequestID filter for log correlation
"""
import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone


class RequestIDFilter(logging.Filter):
    """Inject request_id into every log record."""

    def filter(self, record):
        from flask import g, has_request_context
        if has_request_context():
            record.request_id = getattr(g, 'request_id', None)
        else:
            record.request_id = None
        return True


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production."""

    def format(self, record):
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        if record.request_id:
            log_entry['request_id'] = record.request_id
        if record.exc_info and record.exc_info[0] is not None:
            log_entry['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(app):
    """Configure application logging based on Flask config."""
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
    log_file = app.config.get('LOG_FILE', 'logs/healthcare.log')
    is_production = app.config.get('ENV') == 'production' or not app.config.get('DEBUG')

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove default handlers
    root_logger.handlers.clear()

    request_id_filter = RequestIDFilter()

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.addFilter(request_id_filter)
    if is_production:
        console.setFormatter(JSONFormatter())
    else:
        console.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s [%(request_id)s]: %(message)s'
        ))
    root_logger.addHandler(console)

    # Rotating file handler (production only)
    if is_production and log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10,
            encoding='utf-8',
        )
        file_handler.setLevel(log_level)
        file_handler.addFilter(request_id_filter)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # Silence noisy libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    app.logger.info("Logging initialized (level=%s, file=%s)", app.config.get('LOG_LEVEL'), log_file)
