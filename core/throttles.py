"""
Custom DRF throttle classes for AESTHETIC WAY API.
"""
from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    scope = "register"


class OtpVerifyThrottle(AnonRateThrottle):
    scope = "otp_verify"


class OtpResendThrottle(AnonRateThrottle):
    scope = "otp_resend"


class ForgotPasswordThrottle(AnonRateThrottle):
    scope = "forgot_password"
