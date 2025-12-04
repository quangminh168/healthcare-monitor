import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
mail = Mail()

login_manager.login_view = "main.login"
login_manager.login_message_category = "info"


def create_app():
    app = Flask(__name__)

    # Load config
    app.config.from_object("config.Config")

    # Init extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    # Register blueprints
    from healthcare.routes import main
    app.register_blueprint(main)

    return app
