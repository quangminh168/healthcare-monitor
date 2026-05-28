"""Prometheus metrics for the application.

Exposes:
- http_requests_total (counter)
- http_request_duration_seconds (histogram)
- http_errors_total (counter)
- /metrics endpoint
"""
import time
from flask import Blueprint, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

ERROR_COUNT = Counter(
    'http_errors_total',
    'Total HTTP errors (4xx/5xx)',
    ['method', 'endpoint', 'status'],
)

metrics_bp = Blueprint('metrics', __name__)


@metrics_bp.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


def setup_metrics(app):
    """Register Prometheus before/after request hooks."""

    @app.before_request
    def start_timer():
        request._start_time = time.monotonic()

    @app.after_request
    def record_metrics(response):
        if request.path == '/metrics':
            return response

        duration = time.monotonic() - getattr(request, '_start_time', time.monotonic())
        endpoint = request.endpoint or 'unknown'
        method = request.method
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

        if response.status_code >= 400:
            ERROR_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()

        return response

    app.register_blueprint(metrics_bp)
