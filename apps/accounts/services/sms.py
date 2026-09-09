"""
SMS Provider Abstraction for AESTHETIC WAY.

Architecture:
- BaseSmsProvider: abstract interface
- ConsoleSmsProvider: logs to stdout (development)
- MockSmsProvider: stores sent messages in memory (tests)
- Provider is selected via settings.SMS_PROVIDER

Future: UniFonic, Twilio providers implement BaseSmsProvider without changing callers.
"""
import abc
import logging
from typing import ClassVar

from django.conf import settings

logger = logging.getLogger(__name__)


class BaseSmsProvider(abc.ABC):
    """Abstract SMS provider interface."""

    @abc.abstractmethod
    def send_otp(self, phone: str, code: str, purpose: str) -> bool:
        """
        Send an OTP SMS to the given phone number.

        Args:
            phone: E.164 formatted phone number (+971XXXXXXXXX)
            code: 6-digit OTP string
            purpose: 'registration' | 'login' | 'password_reset'

        Returns:
            True if sent successfully, False otherwise.
        """


class ConsoleSmsProvider(BaseSmsProvider):
    """Development provider � prints OTP to console/logs. Never for production."""

    def send_otp(self, phone: str, code: str, purpose: str) -> bool:
        logger.info(
            "\n" + "=" * 60 +
            f"\n[DEV SMS] OTP for {phone} ({purpose}): {code}" +
            "\n" + "=" * 60
        )
        # Also print to stdout so it is visible in test output
        print(f"\n[DEV SMS] OTP ? {phone} ({purpose}): {code}\n")
        return True


class MockSmsProvider(BaseSmsProvider):
    """
    Test provider � stores sent messages in class-level list.
    Tests can inspect MockSmsProvider.sent_messages to assert OTP delivery.
    """

    sent_messages: ClassVar[list[dict]] = []

    @classmethod
    def reset(cls) -> None:
        """Clear stored messages between tests."""
        cls.sent_messages.clear()

    @classmethod
    def last_otp(cls, phone: str | None = None) -> str | None:
        """Return the most recently sent OTP, optionally filtered by phone."""
        messages = cls.sent_messages
        if phone:
            messages = [m for m in messages if m["phone"] == phone]
        return messages[-1]["code"] if messages else None

    def send_otp(self, phone: str, code: str, purpose: str) -> bool:
        self.__class__.sent_messages.append({"phone": phone, "code": code, "purpose": purpose})
        logger.debug("MockSmsProvider stored OTP %s for %s (%s)", code, phone, purpose)
        return True


def get_sms_provider() -> BaseSmsProvider:
    """
    Factory function � returns the configured SMS provider instance.
    Controlled by settings.SMS_PROVIDER.
    """
    provider_name = getattr(settings, "SMS_PROVIDER", "console").lower()
    providers = {
        "console": ConsoleSmsProvider,
        "mock": MockSmsProvider,
    }
    provider_class = providers.get(provider_name, ConsoleSmsProvider)
    return provider_class()
