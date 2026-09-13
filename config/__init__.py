"""
Django package initialization for AESTHETIC WAY backend.
Ensures Celery app is always imported when Django starts.
"""
from .celery import app as celery_app

__all__ = ("celery_app",)
