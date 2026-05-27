"""Create all database tables.

Run: .venv/Scripts/python.exe -m healthcare.create
"""
from dotenv import load_dotenv
load_dotenv()

from healthcare import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    print("All tables created!")
