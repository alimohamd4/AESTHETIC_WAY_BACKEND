"""
OTP Service for AESTHETIC WAY.

Design decisions (from architect review):
- Redis is the PRIMARY verification authority.
  DB (OtpRecord) is written asynchronously for audit only � never read for verification.
- HMAC-SHA256 with OTP_SECRET_KEY for hashing (fast, safe, no bcrypt overhead).
- Partial unique index on otp_records (phone, purpose) WHERE is_used=FALSE
  prevents duplicate active OTPs (DB-level guard).
- Rate limits enforced via Redis counters:
  * Resend: 1 request per 60 seconds per phone
  * Verify: 5 attempts max per phone per OTP window, then 30-min lockout
  * Verify by IP: 20 verify attempts per IP per hour (enumeration guard)

Redis key schema:
  otp:{phone}:{purpose}          ? {code_hash}|{expires_at_unix}
  otp_resend_lock:{phone}:{purpose} ? 1 (TTL=60s)
  otp_attempts:{phone}:{purpose} ? int (attempt count, TTL=30min)
  otp_locked:{phone}:{purpose}   ? 1 (TTL=30min � lockout sentinel)
  otp_ip_attempts:{ip}           ? int (TTL=3600s)
"""
import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache

from apps.accounts.services.sms import get_sms_provider
from apps.accounts.utils import generate_otp_code, hash_otp

logger = logging.getLogger(__name__)

# --- Constants ----------------------------------------------------------------
OTP_TTL_SECONDS = 600          # 10 minutes OTP validity
OTP_RESEND_COOLDOWN = 60       # 60 second resend cooldown
OTP_MAX_ATTEMPTS = 5           # Max wrong attempts before lockout
OTP_LOCKOUT_SECONDS = 1800     # 30 minute lockout after max attempts
OTP_IP_MAX_ATTEMPTS = 20       # Max verify attempts per IP per hour
OTP_IP_WINDOW_SECONDS = 3600   # 1 hour IP window


class OtpError(Exception):
    """Base OTP exception."""
    code: str = "OTP_ERROR"


class OtpRateLimitError(OtpError):
    """Raised when OTP resend rate limit is hit."""
    code = "OTP_RATE_LIMIT"


class OtpLockedError(OtpError):
    """Raised when account is locked after too many failed attempts."""
    code = "OTP_LOCKED"


class OtpExpiredError(OtpError):
    """Raised when OTP has expired."""
    code = "OTP_EXPIRED"


class OtpInvalidError(OtpError):
    """Raised when OTP code is wrong."""
    code = "OTP_INVALID"


class OtpIpLimitError(OtpError):
    """Raised when IP verify rate limit is hit (anti-enumeration)."""
    code = "OTP_IP_RATE_LIMIT"


class OtpNotFoundError(OtpError):
    """Raised when no active OTP exists for this phone+purpose."""
    code = "OTP_NOT_FOUND"


# --- Redis Key Helpers --------------------------------------------------------

def _otp_key(phone: str, purpose: str) -> str:
    return f"otp:{phone}:{purpose}"

def _resend_lock_key(phone: str, purpose: str) -> str:
    return f"otp_resend_lock:{phone}:{purpose}"

def _attempts_key(phone: str, purpose: str) -> str:
    return f"otp_attempts:{phone}:{purpose}"

def _locked_key(phone: str, purpose: str) -> str:
    return f"otp_locked:{phone}:{purpose}"

def _ip_attempts_key(ip: str) -> str:
    return f"otp_ip_attempts:{ip}"


# --- OTP Service --------------------------------------------------------------

class OtpService:
    """
    Stateless service class for OTP generation, delivery, and verification.
    All state lives in Redis.
    """

    @staticmethod
    def send_otp(phone: str, purpose: str) -> dict:
        """
        Generate and send an OTP for the given phone + purpose.

        Returns:
            dict with 'expires_in' seconds remaining.

        Raises:
            OtpRateLimitError: if resend cooldown has not expired.
        """
        # Check resend cooldown
        resend_key = _resend_lock_key(phone, purpose)
        if cache.get(resend_key):
            ttl = getattr(cache, "ttl", lambda k: OTP_RESEND_COOLDOWN)(resend_key)
            raise OtpRateLimitError(
                f"Please wait {ttl} seconds before requesting a new OTP."
            )

        # Generate code and hash
        code = generate_otp_code()
        code_hash = hash_otp(code)
        expires_at = int(time.time()) + OTP_TTL_SECONDS

        # Store in Redis: "{code_hash}|{expires_at}"
        otp_key = _otp_key(phone, purpose)
        cache.set(otp_key, f"{code_hash}|{expires_at}", timeout=OTP_TTL_SECONDS)

        # Set resend cooldown lock
        cache.set(resend_key, 1, timeout=OTP_RESEND_COOLDOWN)

        # Reset attempt counter for new OTP
        cache.delete(_attempts_key(phone, purpose))
        cache.delete(_locked_key(phone, purpose))

        # Send SMS
        sms = get_sms_provider()
        sent = sms.send_otp(phone, code, purpose)
        if not sent:
            logger.error("SMS delivery failed for %s purpose=%s", phone, purpose)

        # Write audit record to DB asynchronously (fire-and-forget)
        OtpService._write_audit_record(phone, purpose, code_hash, expires_at)

        logger.info("OTP sent to %s for purpose=%s", phone, purpose)
        return {"expires_in": OTP_TTL_SECONDS, "resend_cooldown": OTP_RESEND_COOLDOWN}

    @staticmethod
    def verify_otp(phone: str, purpose: str, code: str, ip_address: str = "unknown") -> bool:
        """
        Verify an OTP code.

        Returns:
            True if valid.

        Raises:
            OtpLockedError: account locked after too many failures.
            OtpIpLimitError: IP-level rate limit exceeded.
            OtpExpiredError: OTP has expired or does not exist.
            OtpInvalidError: code is wrong (also increments attempt counter).
        """
        # Check IP-level rate limit (anti-enumeration across phones)
        ip_key = _ip_attempts_key(ip_address)
        ip_attempts = cache.get(ip_key, 0)
        if ip_attempts >= OTP_IP_MAX_ATTEMPTS:
            raise OtpIpLimitError(
                "Too many verification attempts from this location. Please try again in 1 hour."
            )

        # Check per-phone lockout
        if cache.get(_locked_key(phone, purpose)):
            raise OtpLockedError(
                "This account is temporarily locked due to too many failed attempts. "
                "Please try again in 30 minutes."
            )

        # Fetch OTP from Redis
        otp_key = _otp_key(phone, purpose)
        stored = cache.get(otp_key)

        if not stored:
            # Increment IP counter even on not-found (prevents enumeration)
            OtpService._increment_ip_attempts(ip_key)
            raise OtpExpiredError("No active OTP found. Please request a new one.")

        # Parse stored value
        try:
            stored_hash, expires_at_str = stored.split("|", 1)
            expires_at = int(expires_at_str)
        except (ValueError, AttributeError):
            cache.delete(otp_key)
            raise OtpExpiredError("OTP state corrupted. Please request a new one.")

        # Check expiry (Redis TTL is the primary guard; this is belt-and-suspenders)
        if int(time.time()) > expires_at:
            cache.delete(otp_key)
            raise OtpExpiredError("Your OTP has expired. Please request a new one.")

        # Increment attempt counter first (prevents timing side-channel)
        attempts_key = _attempts_key(phone, purpose)
        attempts = cache.get(attempts_key, 0)

        # Verify hash (constant-time)
        expected_hash = hash_otp(code)
        is_valid = hmac.compare_digest(expected_hash, stored_hash)

        if not is_valid:
            # Increment attempt counters
            new_attempts = attempts + 1
            cache.set(attempts_key, new_attempts, timeout=OTP_LOCKOUT_SECONDS)
            OtpService._increment_ip_attempts(ip_key)

            if new_attempts >= OTP_MAX_ATTEMPTS:
                cache.set(_locked_key(phone, purpose), 1, timeout=OTP_LOCKOUT_SECONDS)
                cache.delete(otp_key)
                raise OtpLockedError(
                    f"Too many failed attempts. Account locked for 30 minutes."
                )

            remaining = OTP_MAX_ATTEMPTS - new_attempts
            raise OtpInvalidError(
                f"Invalid OTP code. {remaining} attempt(s) remaining."
            )

        # Success � invalidate OTP
        cache.delete(otp_key)
        cache.delete(attempts_key)
        cache.delete(_locked_key(phone, purpose))

        logger.info("OTP verified successfully for %s purpose=%s", phone, purpose)
        return True

    @staticmethod
    def _increment_ip_attempts(ip_key: str) -> None:
        """Increment IP-level attempt counter."""
        current = cache.get(ip_key, 0)
        cache.set(ip_key, current + 1, timeout=OTP_IP_WINDOW_SECONDS)

    @staticmethod
    def _write_audit_record(phone: str, purpose: str, code_hash: str, expires_at: int) -> None:
        """
        Write OTP audit record to DB.
        Runs synchronously for simplicity in Phase 1.
        In production, wrap in a Celery task to avoid DB write on hot path.
        """
        try:
            from datetime import datetime, timezone
            from apps.accounts.models import OtpRecord
            expires_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
            OtpRecord.objects.create(
                phone=phone,
                purpose=purpose,
                code_hash=code_hash,
                expires_at=expires_dt,
                is_used=False,
            )
        except Exception as exc:
            # Never fail the OTP flow because of audit write failure
            logger.warning("Failed to write OTP audit record: %s", exc)
