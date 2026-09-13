import logging

from apps.notifications.providers.base import BaseNotificationProvider

logger = logging.getLogger(__name__)


class ConsoleProvider(BaseNotificationProvider):
    """
    Development provider — logs notifications to stdout.
    Set NOTIFICATION_PROVIDER = 'console' in settings.
    """

    def send(self, notification) -> None:
        logger.info(
            "[NOTIFICATION] type=%s recipient=%s payload=%s",
            notification.notification_type,
            notification.recipient_id,
            notification.payload,
        )
