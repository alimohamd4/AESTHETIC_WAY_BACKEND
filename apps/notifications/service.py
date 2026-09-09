from django.conf import settings
from apps.notifications.providers.console_provider import ConsoleProvider
from apps.notifications.providers.mock_provider import MockProvider


def get_notification_provider():
    """
    Factory that returns the configured provider instance.
    Provider is resolved from NOTIFICATION_PROVIDER setting:
      'console' → ConsoleProvider
      'mock'    → MockProvider
    Adding FCM/APNs means adding a new case here.
    """
    provider_name = getattr(settings, "NOTIFICATION_PROVIDER", "console")

    if provider_name == "mock":
        from apps.notifications.providers.mock_provider import MockProvider
        return MockProvider()
    else:
        from apps.notifications.providers.console_provider import ConsoleProvider
        return ConsoleProvider()


class NotificationService:
    """
    High-level service for dispatching notifications.

    Usage:
        NotificationService.send_async(
            recipient=user,
            notification_type=NotificationType.NEW_LEAD_CLINIC,
            payload={"lead_id": str(lead.id), "reference": lead.reference_code},
        )

    The recipient's business state is already committed before this is called.
    This method creates a pending Notification record then dispatches a Celery
    task. If the task fails, only the notification is lost — not business data.
    """

    @staticmethod
    def send_async(recipient, notification_type, payload: dict, channel="push"):
        from apps.notifications.models import Notification, NotificationStatus
        from apps.notifications import tasks as _notification_tasks
        deliver_notification = _notification_tasks.deliver_notification

        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            channel=channel,
            status=NotificationStatus.PENDING,
            payload=payload,
        )

        # Dispatch async — this call must NOT block or raise
        try:
            deliver_notification.delay(str(notification.id))
        except Exception:
            # If Celery/Redis is down, the notification stays pending.
            # A periodic beat task can later sweep pending records.
            import logging
            logging.getLogger(__name__).warning(
                "Failed to enqueue notification %s — will remain pending.", notification.id
            )

        return notification
