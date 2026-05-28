import logging
from flask import g, request, jsonify, render_template

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        logger.warning(
            "404 Not Found: %s %s (request_id=%s)",
            request.method, request.path, getattr(g, 'request_id', None),
        )
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify(error='Not found'), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.exception(
            "500 Internal Server Error: %s %s (request_id=%s)",
            request.method, request.path, getattr(g, 'request_id', None),
        )
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify(error='Internal server error'), 500
        return render_template('errors/500.html'), 500
