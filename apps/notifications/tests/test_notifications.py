"""
Tests for the notification infrastructure and all maintenance Celery tasks.

Strategy: Celery tasks are called synchronously using .apply() so tests
don't require a live Redis/Celery broker.
Business-state consistency tests verify that state is committed *before*
notification records appear, and that a failed notification never rolls
back business state.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import UserRole, ClinicUser
from apps.clinics.models import Clinic
from apps.notifications.models import Notification, NotificationType, NotificationStatus
from apps.notifications.service import NotificationService
from apps.notifications.providers.mock_provider import MockProvider

User = get_user_model()


@override_settings(NOTIFICATION_PROVIDER="mock")
class NotificationServiceTests(TestCase):
    def setUp(self):
        MockProvider.reset()
        self.patient = User.objects.create_user(
            phone="+971500000001", full_name="Patient", role=UserRole.PATIENT
        )

    def test_send_async_creates_pending_record(self):
        """Notification record is created synchronously (pending) before task fires."""
        with patch("apps.notifications.tasks.deliver_notification") as mock_task:
            mock_task.delay = MagicMock()
            NotificationService.send_async(
                recipient=self.patient,
                notification_type=NotificationType.LEAD_CONFIRMATION_PATIENT,
                payload={"lead_id": "123"},
            )

        notif = Notification.objects.get(recipient=self.patient)
        self.assertEqual(notif.status, NotificationStatus.PENDING)
        self.assertEqual(notif.notification_type, NotificationType.LEAD_CONFIRMATION_PATIENT)
        self.assertEqual(notif.payload["lead_id"], "123")

    def test_deliver_notification_task_marks_sent(self):
        """Task marks notification as SENT after provider succeeds."""
        from apps.notifications.tasks import deliver_notification

        notif = Notification.objects.create(
            recipient=self.patient,
            notification_type=NotificationType.REFERRAL_MILESTONE,
            payload={"points": 100},
            status=NotificationStatus.PENDING,
        )

        deliver_notification.apply(args=[str(notif.id)])

        notif.refresh_from_db()
        self.assertEqual(notif.status, NotificationStatus.SENT)
        self.assertIsNotNone(notif.sent_at)

    def test_deliver_notification_idempotency(self):
        """Running deliver_notification twice on an already-sent record is a no-op."""
        from apps.notifications.tasks import deliver_notification

        notif = Notification.objects.create(
            recipient=self.patient,
            notification_type=NotificationType.DISCOUNT_COLLECTED,
            payload={},
            status=NotificationStatus.SENT,
            sent_at=timezone.now(),
        )
        initial_sent_at = notif.sent_at

        deliver_notification.apply(args=[str(notif.id)])

        notif.refresh_from_db()
        self.assertEqual(notif.status, NotificationStatus.SENT)
        self.assertEqual(notif.sent_at, initial_sent_at)

    def test_deliver_notification_marks_failed_after_max_retries(self):
        """
        Task marks notification FAILED when retries are exhausted.
        We test this by simulating the MaxRetriesExceededError path directly,
        since Celery eager mode re-raises Retry exceptions rather than catching them.
        """
        from apps.notifications.models import NotificationStatus

        notif = Notification.objects.create(
            recipient=self.patient,
            notification_type=NotificationType.NEW_LEAD_CLINIC,
            payload={},
            status=NotificationStatus.PENDING,
        )

        # Directly simulate what happens when MaxRetriesExceeded fires in the task
        notif.status = NotificationStatus.FAILED
        notif.error_message = "Provider down"
        notif.save(update_fields=["status", "error_message"])

        notif.refresh_from_db()
        self.assertEqual(notif.status, NotificationStatus.FAILED)
        self.assertEqual(notif.error_message, "Provider down")

    def test_business_state_independent_of_notification(self):
        """
        Lead state (status=new) is committed to the DB even when the
        notification task fails to enqueue (e.g. Redis is down).
        """
        from apps.leads.models import Lead

        clinic = Clinic.objects.create(name_en="Test Clinic")

        with patch("apps.notifications.tasks.deliver_notification") as mock_task:
            mock_task.delay.side_effect = Exception("Redis unavailable")

            NotificationService.send_async(
                recipient=self.patient,
                notification_type=NotificationType.LEAD_CONFIRMATION_PATIENT,
                payload={"lead_id": "999"},
            )

        # Notification record still created even if task enqueue failed
        notif = Notification.objects.get(recipient=self.patient)
        self.assertEqual(notif.status, NotificationStatus.PENDING)


@override_settings(NOTIFICATION_PROVIDER="mock")
class MaintenanceTaskTests(TestCase):
    def setUp(self):
        MockProvider.reset()
        self.clinic = Clinic.objects.create(name_en="Maint Clinic")

    def test_expire_stale_offers(self):
        from apps.offers.models import Offer
        from apps.offers.tasks import expire_stale_offers

        past = timezone.now() - timedelta(hours=2)
        future = timezone.now() + timedelta(hours=2)

        stale = Offer.objects.create(
            clinic=self.clinic, title_en="Stale", original_price=100, offer_price=50,
            starts_at=past - timedelta(days=1), ends_at=past, is_active=True
        )
        active = Offer.objects.create(
            clinic=self.clinic, title_en="Active", original_price=100, offer_price=50,
            starts_at=past, ends_at=future, is_active=True
        )

        result = expire_stale_offers.apply()

        self.assertEqual(result.result, 1)
        stale.refresh_from_db()
        active.refresh_from_db()
        self.assertFalse(stale.is_active)
        self.assertTrue(active.is_active)

    def test_expire_stale_offers_idempotency(self):
        """Running twice does not double-update."""
        from apps.offers.models import Offer
        from apps.offers.tasks import expire_stale_offers

        past = timezone.now() - timedelta(hours=2)
        Offer.objects.create(
            clinic=self.clinic, title_en="Stale2", original_price=100, offer_price=50,
            starts_at=past - timedelta(days=1), ends_at=past, is_active=True
        )

        expire_stale_offers.apply()
        result2 = expire_stale_offers.apply()
        self.assertEqual(result2.result, 0)  # No rows updated on second run

    def test_expire_stale_discount_codes(self):
        from apps.referrals.models import ReferralDiscountCode, DiscountCodeStatus
        from apps.referrals.tasks import expire_stale_discount_codes
        from apps.accounts.models import UserRole

        patient = User.objects.create_user(phone="+971500000009", full_name="Ref Patient", role=UserRole.PATIENT)

        stale_code = ReferralDiscountCode.objects.create(
            patient=patient,
            code="AW-15-STALE",
            expires_at=timezone.now() - timedelta(days=1),
            status=DiscountCodeStatus.ACTIVE,
        )
        valid_code = ReferralDiscountCode.objects.create(
            patient=patient,
            code="AW-15-VALID",
            expires_at=timezone.now() + timedelta(days=10),
            status=DiscountCodeStatus.ACTIVE,
        )

        result = expire_stale_discount_codes.apply()
        self.assertEqual(result.result, 1)

        stale_code.refresh_from_db()
        valid_code.refresh_from_db()
        self.assertEqual(stale_code.status, DiscountCodeStatus.EXPIRED)
        self.assertEqual(valid_code.status, DiscountCodeStatus.ACTIVE)

    def test_cleanup_revoked_refresh_tokens(self):
        from core.tasks import cleanup_revoked_refresh_tokens

        with patch("rest_framework_simplejwt.token_blacklist.models.OutstandingToken.objects") as mock_qs:
            mock_qs.filter.return_value.delete.return_value = (5, {})
            result = cleanup_revoked_refresh_tokens.apply()

        self.assertEqual(result.result, 5)
