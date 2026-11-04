"""E-mail verification with 6-digit one-time codes."""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import EmailCode

CODE_LENGTH = 6


def _hash(user, code):
    message = f"{user.pk}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def seconds_until_resend(user):
    latest = user.email_codes.first()
    if not latest:
        return 0
    wait = (latest.created_at + EmailCode.RESEND_COOLDOWN - timezone.now()).total_seconds()
    return max(0, int(wait + 0.999))


def send_code(user, *, force=False):
    """E-mail a fresh code to the user's address. Returns seconds to wait if called too soon, else 0."""
    wait = seconds_until_resend(user)
    if wait and not force:
        return wait
    code = f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"
    user.email_codes.filter(used=False).update(used=True)  # only the newest code works
    EmailCode.objects.create(user=user, email=user.email, code_hash=_hash(user, code))
    send_mail(
        subject=f"{code} is your ReCode code",
        message=f"Your ReCode verification code is {code}\n\nIt expires in 15 minutes.",
        from_email=None,
        recipient_list=[user.email],
    )
    return 0


def check_code(user, code):
    """Returns one of: verified, wrong, expired, locked, missing — plus attempts left."""
    entry = user.email_codes.filter(used=False).first()
    if not entry or entry.email != user.email:
        return "missing", 0
    if entry.expired:
        return "expired", 0
    if entry.attempts >= EmailCode.MAX_ATTEMPTS:
        return "locked", 0
    code = "".join(ch for ch in str(code) if ch.isdigit())
    if len(code) == CODE_LENGTH and hmac.compare_digest(entry.code_hash, _hash(user, code)):
        entry.used = True
        entry.save(update_fields=["used"])
        profile = user.profile
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
        return "verified", 0
    entry.attempts += 1
    entry.save(update_fields=["attempts"])
    left = EmailCode.MAX_ATTEMPTS - entry.attempts
    return ("wrong" if left else "locked"), left


def mask_email(email):
    name, _, domain = email.partition("@")
    if not domain:
        return email
    visible = name[:2] if len(name) > 2 else name[:1]
    return f"{visible}{'•' * min(4, max(1, len(name) - len(visible)))}@{domain}"
