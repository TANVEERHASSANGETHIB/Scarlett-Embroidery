import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.utils import send_templated_email

from .models import EmailVerification, User


def _hash_code(user_id, code):
    msg = f"{user_id}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def generate_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def seconds_until_resend(user):
    latest = user.verifications.first()
    if not latest:
        return 0
    elapsed = (timezone.now() - latest.created_at).total_seconds()
    return max(0, int(settings.VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed))


@transaction.atomic
def issue_verification_code(user):
    """Invalidate outstanding codes, create a new one and email it. Returns the plain code."""
    now = timezone.now()
    user.verifications.filter(consumed_at__isnull=True).update(consumed_at=now)
    code = generate_code()
    EmailVerification.objects.create(
        user=user,
        code_hash=_hash_code(user.pk, code),
        expires_at=now + timedelta(minutes=settings.VERIFICATION_CODE_TTL_MINUTES),
    )
    transaction.on_commit(
        lambda: send_templated_email(
            f"{code} is your Scarlett Embroidery verification code",
            "verification_code",
            {"user": user, "code": code, "ttl": settings.VERIFICATION_CODE_TTL_MINUTES},
            user.email,
        )
    )
    return code


@dataclass
class VerifyResult:
    ok: bool
    error: str = ""


@transaction.atomic
def verify_code(user: User, code: str) -> VerifyResult:
    code = (code or "").strip().replace(" ", "")
    record = (
        EmailVerification.objects.select_for_update()
        .filter(user=user, consumed_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if record is None or record.is_expired:
        return VerifyResult(False, "This code has expired. Request a new one.")
    if record.attempts >= settings.VERIFICATION_CODE_MAX_ATTEMPTS:
        return VerifyResult(False, "Too many incorrect attempts. Request a new code.")

    if not hmac.compare_digest(record.code_hash, _hash_code(user.pk, code)):
        record.attempts += 1
        record.save(update_fields=["attempts"])
        remaining = settings.VERIFICATION_CODE_MAX_ATTEMPTS - record.attempts
        if remaining <= 0:
            return VerifyResult(False, "Too many incorrect attempts. Request a new code.")
        return VerifyResult(False, f"That code is not correct. {remaining} attempt(s) left.")

    record.consumed_at = timezone.now()
    record.save(update_fields=["consumed_at"])
    user.email_verified = True
    user.save(update_fields=["email_verified"])
    return VerifyResult(True)
