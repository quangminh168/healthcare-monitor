from flask import Blueprint, jsonify
from healthcare import db

health_bp = Blueprint('health', __name__)


@health_bp.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'database': str(e)}), 503
