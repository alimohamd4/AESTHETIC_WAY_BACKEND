import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="referrals.expire_stale_discount_codes")
def expire_stale_discount_codes():
    """
    Idempotent: marks active ReferralDiscountCodes past their expires_at as 'expired'.
    """
    from apps.referrals.models import ReferralDiscountCode, DiscountCodeStatus

    updated = ReferralDiscountCode.objects.filter(
        expires_at__lt=timezone.now(),
        status=DiscountCodeStatus.ACTIVE,
    ).update(status=DiscountCodeStatus.EXPIRED)

    logger.info("expire_stale_discount_codes: expired %d code(s).", updated)
    return updated
