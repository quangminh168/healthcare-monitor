"""Create the device_api_key table and seed a key for existing devices."""
from dotenv import load_dotenv
load_dotenv()

from healthcare import app, db
from healthcare.models import DeviceApiKey, Post

with app.app_context():
    db.create_all()

    # Seed API keys for all device_ids that have posts but no key yet
    device_ids = {p.device_id for p in Post.query.all()}
    existing = {k.device_id for k in DeviceApiKey.query.all()}

    for device_id in device_ids - existing:
        key = DeviceApiKey(device_id=device_id)
        db.session.add(key)
        db.session.commit()
        print(f"Created API key for device '{device_id}': {key.api_key}")

    for entry in DeviceApiKey.query.all():
        print(f"  {entry.device_id} -> {entry.api_key}")
