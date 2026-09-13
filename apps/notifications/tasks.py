import logging

from celery import shared_task
from django.utils import timezone

from apps.notifications.service import get_notification_provider

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute, then doubles
    acks_late=True,
)
def deliver_notification(self, notification_id: str):
    """
    Deliver a single Notification record via the configured provider.
    Retries up to 3 times with exponential backoff on failure.
    Business state is NEVER changed here — only notification status.
    """
    from apps.notifications.models import Notification, NotificationStatus

    try:
        notification = Notification.objects.get(id=notification_id)
    except Notification.DoesNotExist:
        logger.warning("deliver_notification: Notification %s not found — skipping.", notification_id)
        return

    if notification.status == NotificationStatus.SENT:
        # Idempotency guard: already delivered (e.g. duplicate task)
        return

    try:
        provider = get_notification_provider()
        provider.send(notification)

        notification.status = NotificationStatus.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "sent_at"])

        logger.info("Notification %s delivered via %s.", notification_id, provider.__class__.__name__)

    except Exception as exc:
        logger.error("Notification %s failed: %s", notification_id, exc)

        countdown = 60 * (2 ** self.request.retries)  # exponential: 60s, 120s, 240s
        try:
            raise self.retry(exc=exc, countdown=countdown)
        except self.MaxRetriesExceededError:
            notification.status = NotificationStatus.FAILED
            notification.error_message = str(exc)
            notification.save(update_fields=["status", "error_message"])
