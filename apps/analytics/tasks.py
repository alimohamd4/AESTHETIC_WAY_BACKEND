import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta, date

logger = logging.getLogger(__name__)


@shared_task(name="analytics.daily_rollup")
def analytics_daily_rollup():
    """
    Idempotent daily aggregation of analytics events for yesterday.
    Stores a JSON summary in the Django cache keyed by date.
    Running twice on the same date simply overwrites with the same result.
    """
    from django.core.cache import cache
    from apps.analytics.models import AnalyticsEvent

    yesterday = (timezone.now() - timedelta(days=1)).date()
    start = timezone.datetime.combine(yesterday, timezone.datetime.min.time(), tzinfo=timezone.get_current_timezone())
    end = start + timedelta(days=1)

    qs = AnalyticsEvent.objects.filter(timestamp__gte=start, timestamp__lt=end)
    summary = {}
    for event_type, _ in AnalyticsEvent._meta.get_field("event_type").choices:
        summary[event_type] = qs.filter(event_type=event_type).count()

    cache_key = f"analytics_rollup_{yesterday.isoformat()}"
    cache.set(cache_key, summary, timeout=60 * 60 * 24 * 30)  # 30 days

    logger.info("analytics_daily_rollup: stored rollup for %s → %s", yesterday, summary)
    return summary
