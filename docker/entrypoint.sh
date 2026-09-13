#!/bin/sh
set -e

# ==============================================================================
# AESTHETIC WAY Backend Production Entrypoint Script
# ==============================================================================

echo "==> [Entrypoint] Starting AESTHETIC WAY service container..."

# 1. Wait for Database if DB_HOST is defined
if [ -n "$DB_HOST" ]; then
    DB_PORT="${DB_PORT:-5432}"
    echo "==> [Entrypoint] Waiting for database at $DB_HOST:$DB_PORT..."
    python - <<END
import socket
import time
import sys

host = "$DB_HOST"
port = int("$DB_PORT")
start_time = time.time()
timeout = 60

while True:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((host, port))
        sock.close()
        print("==> [Entrypoint] Database is ready and accepting connections!")
        sys.exit(0)
    except Exception:
        if time.time() - start_time > timeout:
            print("==> [Entrypoint] ERROR: Timeout waiting for database connection.")
            sys.exit(1)
        time.sleep(1)
END
fi

# 2. Wait for Redis if REDIS_URL is defined
if [ -n "$REDIS_URL" ]; then
    echo "==> [Entrypoint] Verifying Redis connectivity..."
    python - <<END
import time
import sys
from urllib.parse import urlparse
import socket

redis_url = "$REDIS_URL"
parsed = urlparse(redis_url)
host = parsed.hostname or "localhost"
port = parsed.port or 6379

start_time = time.time()
timeout = 60

while True:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((host, port))
        sock.close()
        print("==> [Entrypoint] Redis is ready and reachable!")
        sys.exit(0)
    except Exception:
        if time.time() - start_time > timeout:
            print("==> [Entrypoint] ERROR: Timeout waiting for Redis.")
            sys.exit(1)
        time.sleep(1)
END
fi

# 3. For web process: run database migrations and collect static assets
# Do not run migrations or collectstatic for Celery workers or Beat
if [ "$1" != "celery" ]; then
    echo "==> [Entrypoint] Applying database migrations..."
    python manage.py migrate --noinput

    echo "==> [Entrypoint] Collecting static assets..."
    python manage.py collectstatic --noinput --clear
fi

echo "==> [Entrypoint] Ready. Executing command: $@"
exec "$@"
