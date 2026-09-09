from apps.notifications.providers.base import BaseNotificationProvider


class MockProvider(BaseNotificationProvider):
    """
    In-memory provider for tests.
    Stores sent notifications in ``MockProvider.sent`` for assertion.
    Set NOTIFICATION_PROVIDER = 'mock' in testing settings.
    """

    sent: list = []

    @classmethod
    def reset(cls):
        cls.sent = []

    def send(self, notification) -> None:
        self.sent.append({
            "id": str(notification.id),
            "type": notification.notification_type,
            "recipient_id": str(notification.recipient_id),
            "payload": notification.payload,
        })
