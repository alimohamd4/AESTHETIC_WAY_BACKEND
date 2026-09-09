import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="core.cleanup_revoked_refresh_tokens")
def cleanup_revoked_refresh_tokens():
    """
    Idempotent: removes expired JWT outstanding tokens from the simplejwt blacklist.
    Outstanding tokens with expiry in the past can never be refreshed again —
    safe to permanently delete them to keep the table lean.
    """
    try:
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

        deleted_count, _ = OutstandingToken.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()

        logger.info("cleanup_revoked_refresh_tokens: removed %d expired token(s).", deleted_count)
        return deleted_count

    except Exception as exc:
        logger.error("cleanup_revoked_refresh_tokens failed: %s", exc)
        raise
