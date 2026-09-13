"""
Celery application configuration for AESTHETIC WAY backend.
"""
import logging
import os

from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("aesthetic_way")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks([
    "apps.notifications",
    "apps.offers",
    "apps.referrals",
    "apps.analytics",
    "core",
])


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    logger.debug("Request: %r", self.request)


app.conf.beat_schedule = {
    # Expire stale offers every hour
    "expire-stale-offers": {
        "task": "offers.expire_stale_offers",
        "schedule": crontab(minute=0),  # top of every hour
    },
    # Expire stale discount codes every 6 hours
    "expire-stale-discount-codes": {
        "task": "referrals.expire_stale_discount_codes",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # Analytics daily rollup at 01:00 Dubai time
    "analytics-daily-rollup": {
        "task": "analytics.daily_rollup",
        "schedule": crontab(minute=0, hour=1),
    },
    # Cleanup expired JWT tokens at 02:00 Dubai time
    "cleanup-revoked-refresh-tokens": {
        "task": "core.cleanup_revoked_refresh_tokens",
        "schedule": crontab(minute=0, hour=2),
    },
}
