from django.db import transaction
from django.db.models import Sum
from apps.referrals.models import ReferralPointsLedger, LedgerTransactionType
from apps.accounts.models import PatientProfile


def award_referral_milestones(patient):
    """
    Evaluates total successful invites and awards milestones idempotently.
    Updates PatientProfile.current_points based on the ledger sum.
    Notifications fire AFTER the transaction commits.
    """
    newly_awarded = []

    with transaction.atomic():
        profile = PatientProfile.objects.select_for_update().get(user=patient)
        invites_count = profile.total_successful_invites

        milestones = [
            (20, LedgerTransactionType.MILESTONE_20, 100),
            (35, LedgerTransactionType.MILESTONE_35, 175),
            (50, LedgerTransactionType.MILESTONE_50, 250),
        ]

        for threshold, txn_type, points in milestones:
            if invites_count >= threshold:
                idempotency_key = f"{txn_type}_{patient.id}"

                # get_or_create ensures we never award the same milestone twice
                _, created = ReferralPointsLedger.objects.get_or_create(
                    idempotency_key=idempotency_key,
                    defaults={
                        "patient": patient,
                        "transaction_type": txn_type,
                        "points": points
                    }
                )
                if created:
                    newly_awarded.append({"threshold": threshold, "points": points})

        # Recalculate total points from ledger
        ledger_sum = ReferralPointsLedger.objects.filter(patient=patient).aggregate(Sum("points"))["points__sum"] or 0
        profile.current_points = ledger_sum
        profile.save(update_fields=["current_points"])

    # --- Notifications (fire-and-forget, outside the transaction) ---
    if newly_awarded:
        from apps.notifications.service import NotificationService
        from apps.notifications.models import NotificationType

        for award in newly_awarded:
            NotificationService.send_async(
                recipient=patient,
                notification_type=NotificationType.REFERRAL_MILESTONE,
                payload={
                    "threshold": award["threshold"],
                    "points_awarded": award["points"],
                    "total_points": profile.current_points,
                },
            )

