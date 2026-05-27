"""Production entry point for gunicorn.

Usage:
    gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
"""
import os
from dotenv import load_dotenv
load_dotenv()

from healthcare import create_app

app = create_app()
