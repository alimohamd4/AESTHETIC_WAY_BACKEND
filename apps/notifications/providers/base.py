from abc import ABC, abstractmethod


class BaseNotificationProvider(ABC):
    """
    Abstract provider interface.
    Concrete implementations: ConsoleProvider, MockProvider, FCMProvider, APNsProvider, SMSProvider.
    """

    @abstractmethod
    def send(self, notification) -> None:
        """
        Deliver the notification.
        Should raise an exception on failure so the Celery task can retry.

        :param notification: Notification model instance
        """
        raise NotImplementedError
