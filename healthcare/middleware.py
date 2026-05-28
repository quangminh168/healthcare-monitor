"""Request middleware for logging and monitoring."""
import uuid
from flask import g, request


def setup_middleware(app):
    """Register before/after request hooks."""

    @app.before_request
    def assign_request_id():
        g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())

    @app.after_request
    def set_request_id_header(response):
        request_id = getattr(g, 'request_id', None)
        if request_id:
            response.headers['X-Request-ID'] = request_id
        return response
