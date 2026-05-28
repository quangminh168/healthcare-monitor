import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import config

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
mail = Mail()
limiter = Limiter(get_remote_address, storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'))


def create_app(config_name=None):
    app = Flask(__name__)

    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app.config.from_object(config[config_name])

    if config_name == 'production':
        if not app.config.get('SECRET_KEY'):
            raise ValueError("SECRET_KEY must be set in production")
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            raise ValueError("SQLALCHEMY_DATABASE_URI must be set in production")

    if app.config.get('DEBUG', False):
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.jinja_env.auto_reload = True
        app.jinja_env.cache = {}

    db.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    limiter.init_app(app)

    # Logging (structured, rotating)
    from healthcare.logging_config import setup_logging
    setup_logging(app)

    # Request ID middleware
    from healthcare.middleware import setup_middleware
    setup_middleware(app)

    # Prometheus metrics
    if app.config.get('METRICS_ENABLED', True):
        from healthcare.metrics import setup_metrics
        setup_metrics(app)

    # Celery (tasks use db, mail via ContextTask app context)
    from celery_worker import celery as celery_app
    celery_app.conf.update(
        broker_url=app.config.get('CELERY_BROKER_URL', os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')),
        result_backend=app.config.get('CELERY_RESULT_BACKEND', os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')),
    )

    from healthcare.auth_routes import auth_bp
    from healthcare.api_routes import api_bp
    from healthcare.dashboard_routes import dashboard_bp
    from healthcare.health import health_bp
    from healthcare.errors import register_error_handlers

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(health_bp)
    register_error_handlers(app)

    return app
