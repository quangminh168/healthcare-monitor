"""Migration: add is_critical to HeartRateData, create aggregation tables.

Safe to run multiple times — catches 'already exists' / 'duplicate column'.

Run: .venv/Scripts/python.exe migrate_retention.py
"""
from dotenv import load_dotenv
load_dotenv()

from healthcare import app, db

with app.app_context():
    dialect = db.engine.dialect.name
    print(f"Database dialect: {dialect}")

    with db.engine.connect() as conn:
        # 1. Add is_critical column to heart_rate_data
        try:
            if dialect == "mysql":
                conn.execute(db.text(
                    "ALTER TABLE heart_rate_data ADD COLUMN is_critical BOOLEAN NOT NULL DEFAULT 0"
                ))
            else:
                conn.execute(db.text(
                    "ALTER TABLE heart_rate_data ADD COLUMN is_critical BOOLEAN NOT NULL DEFAULT 0"
                ))
            conn.commit()
            print("  Added: heart_rate_data.is_critical")
        except Exception as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                print("  Exists: heart_rate_data.is_critical")
            else:
                print(f"  Error:  heart_rate_data.is_critical -- {e}")

        # 2. Create aggregation tables
        try:
            from healthcare.models import HeartRateHourly, HeartRateDaily  # noqa: F401
            db.create_all()
            print("  Created: heart_rate_hourly, heart_rate_daily")
        except Exception as e:
            print(f"  Tables: {e}")

        # 3. Backfill is_critical for existing data
        try:
            result = conn.execute(db.text(
                "UPDATE heart_rate_data SET is_critical = 1 "
                "WHERE heart_rate < 40 OR heart_rate > 180 OR spo2 < 85"
            ))
            conn.commit()
            print(f"  Backfilled: {result.rowcount} critical readings flagged")
        except Exception as e:
            print(f"  Backfill: {e}")

        # 4. Verify
        print("\nVerification:")
        if dialect == "mysql":
            result = conn.execute(db.text("SHOW COLUMNS FROM heart_rate_data"))
            cols = [row[0] for row in result.fetchall()]
            print(f"  heart_rate_data columns: {cols}")

            result = conn.execute(db.text("SELECT COUNT(*) FROM heart_rate_data WHERE is_critical = 1"))
            print(f"  Critical readings: {result.fetchone()[0]}")

            for table in ["heart_rate_hourly", "heart_rate_daily"]:
                try:
                    result = conn.execute(db.text(f"SELECT COUNT(*) FROM {table}"))
                    print(f"  {table}: {result.fetchone()[0]} rows")
                except Exception:
                    print(f"  {table}: does not exist yet")

    print("\nDone.")
