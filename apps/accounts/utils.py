"""
Utility functions for the accounts app.
"""
import hashlib
import hmac
import secrets
import string

from django.conf import settings


def generate_referral_code() -> str:
    """
    Generate a unique patient referral code in the format AW-{4ALPHANUM}-{4ALPHANUM}.
    Uniqueness is enforced by the DB UNIQUE constraint; retry on collision is handled by caller.
    """
    chars = string.ascii_uppercase + string.digits
    part1 = "".join(secrets.choice(chars) for _ in range(4))
    part2 = "".join(secrets.choice(chars) for _ in range(4))
    return f"AW-{part1}-{part2}"


def generate_otp_code() -> str:
    """Generate a cryptographically random 6-digit OTP code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(code: str) -> str:
    """
    Hash an OTP code using HMAC-SHA256 with the OTP_SECRET_KEY.
    Fast and secure for 6-digit codes. No bcrypt needed.
    """
    secret = getattr(settings, "OTP_SECRET_KEY", settings.SECRET_KEY)
    return hmac.new(
        secret.encode(),
        code.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_otp_hash(code: str, code_hash: str) -> bool:
    """Verify an OTP code against its stored hash. Timing-safe comparison."""
    expected_hash = hash_otp(code)
    return hmac.compare_digest(expected_hash, code_hash)


def generate_discount_code() -> str:
    """
    Generate a discount code in format AW-15-{6RANDOM_ALPHANUM}.
    36^6 = ~2.1B combinations � effectively no collision risk.
    """
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(6))
    return f"AW-15-{suffix}"


def generate_lead_reference() -> str:
    """
    Generate a lead reference code: REQ-{8_RANDOM_DIGITS}.
    No hash prefix � client displays '#REQ-...' by convention.
    """
    digits = "".join(str(secrets.randbelow(10)) for _ in range(8))
    return f"REQ-{digits}"


def normalize_phone(phone: str) -> str:
    """
    Normalize a UAE phone number to E.164 format (+971XXXXXXXXX).
    Returns the cleaned phone number or raises ValueError.
    """
    import phonenumbers
    try:
        parsed = phonenumbers.parse(phone, "AE")
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError(f"Invalid phone number: {phone}")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.phonenumberutil.NumberParseException as e:
        raise ValueError(f"Cannot parse phone number: {phone}") from e
