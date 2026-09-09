"""
Signal handlers for the accounts app.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PatientProfile, User, UserRole

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
    """
    Automatically create a PatientProfile when a patient User is created.
    The referral code is generated here.
    """
    if created and instance.role == UserRole.PATIENT:
        from apps.accounts.utils import generate_referral_code
        referral_code = generate_referral_code()
        PatientProfile.objects.create(
            user=instance,
            referral_code=referral_code,
        )
        logger.info("PatientProfile created for user %s with code %s", instance.id, referral_code)
