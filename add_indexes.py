"""Add indexes to HeartRateData and Post tables.

Safe to run multiple times — catches 'Duplicate key name' for MySQL
and 'already exists' for SQLite.

Run: .venv/Scripts/python.exe add_indexes.py
"""
from dotenv import load_dotenv
load_dotenv()

from healthcare import app, db
from healthcare.models import HeartRateData, Post

with app.app_context():
    dialect = db.engine.dialect.name
    hrd_table = HeartRateData.__tablename__
    post_table = Post.__tablename__

    print(f"Database dialect: {dialect}")
    print(f"HeartRateData table: {hrd_table}")
    print(f"Post table: {post_table}")

    indexes = [
        # Composite: covers ALL HeartRateData queries (filter+order+limit).
        # Left-prefix also covers device_id-only lookups.
        ("idx_hrd_device_timestamp", hrd_table, ["device_id", "timestamp"]),
        # Post.device_id lookup (api_routes.py line 89)
        ("idx_post_device_id", post_table, ["device_id"]),
    ]

    with db.engine.connect() as conn:
        for idx_name, table, columns in indexes:
            cols = ", ".join(columns)
            try:
                conn.execute(db.text(f"CREATE INDEX {idx_name} ON {table} ({cols})"))
                conn.commit()
                print(f"  Created: {idx_name} on {table}({cols})")
            except Exception as e:
                err = str(e).lower()
                if "duplicate" in err or "already exists" in err:
                    print(f"  Exists:  {idx_name} on {table}({cols})")
                else:
                    print(f"  Error:   {idx_name} -- {e}")

        # Verify
        print("\nVerification:")
        if dialect == "mysql":
            for table in [hrd_table, post_table]:
                result = conn.execute(db.text(f"SHOW INDEX FROM {table}"))
                rows = result.fetchall()
                idx_names = sorted(set(row[2] for row in rows))
                print(f"  {table}: {idx_names}")
        elif dialect == "sqlite":
            for table in [hrd_table, post_table]:
                result = conn.execute(db.text(f"PRAGMA index_list({table})"))
                rows = result.fetchall()
                print(f"  {table}: {[row[1] for row in rows]}")

    print("\nDone.")
