#!/bin/sh
set -e

echo "Waiting for MySQL..."
while ! python -c "
import pymysql, os
from urllib.parse import urlparse
uri = os.environ.get('SQLALCHEMY_DATABASE_URI', '')
p = urlparse(uri)
try:
    pymysql.connect(host=p.hostname, user=p.username, password=p.password, database=p.path.lstrip('/'))
    print('MySQL ready')
except Exception:
    exit(1)
" 2>/dev/null; do
    sleep 2
done

echo "Creating database tables..."
python -c "
from dotenv import load_dotenv
load_dotenv()
from healthcare import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print('Tables ready')
"

echo "Starting application..."
exec "$@"
