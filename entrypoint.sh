#!/bin/sh
set -e

# Fail-fast: validate SQLALCHEMY_DATABASE_URI
URI="${SQLALCHEMY_DATABASE_URI:-}"
if [ -z "$URI" ]; then
    echo "FATAL: SQLALCHEMY_DATABASE_URI is not set. Check .env and docker-compose environment."
    exit 1
fi

echo "Waiting for MySQL..."
while ! python -c "
import pymysql, os
from urllib.parse import urlparse
uri = os.environ.get('SQLALCHEMY_DATABASE_URI', '')
p = urlparse(uri)
if not p.hostname:
    print('FATAL: SQLALCHEMY_DATABASE_URI has no hostname:', uri)
    exit(2)
try:
    pymysql.connect(host=p.hostname, user=p.username, password=p.password, database=p.path.lstrip('/'), connect_timeout=5)
    print('MySQL ready')
except Exception as e:
    exit(1)
" 2>/dev/null; do
    # Check for fatal parse errors (exit code 2)
    result=$?
    if [ "$result" -eq 2 ]; then
        echo "FATAL: Invalid SQLALCHEMY_DATABASE_URI. Exiting."
        exit 1
    fi
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
