# Multi-stage production Dockerfile for AESTHETIC WAY Backend
# Python 3.13 / Debian Slim base

FROM python:3.13-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create application unprivileged user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy application source
COPY . /app

# Create required directories for static and media files with proper permissions
RUN mkdir -p /app/staticfiles /app/mediafiles && \
    chown -R appuser:appuser /app

# Setup entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Switch to unprivileged user
USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
