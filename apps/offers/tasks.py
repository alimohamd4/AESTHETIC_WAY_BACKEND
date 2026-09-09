import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="offers.expire_stale_offers")
def expire_stale_offers():
    """
    Idempotent: marks all offers whose ends_at < now as is_active=False.
    Safe to run multiple times — only updates rows that actually need it.
    """
    from apps.offers.models import Offer

    updated = Offer.objects.filter(
        ends_at__lt=timezone.now(),
        is_active=True,
    ).update(is_active=False, status="suspended")

    logger.info("expire_stale_offers: deactivated %d offer(s).", updated)
    return updated
