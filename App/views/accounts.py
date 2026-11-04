from django.contrib import messages
import time

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .. import verification
from ..forms import EmailForm, RegisterForm
from .helpers import json_body
from .verify import MESSAGES as VERIFY_MESSAGES


def _next_url(request, default="/dashboard/"):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return default


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():  # all or nothing: never leave a half-made account
            user = form.save()
        login(request, user)
        try:
            verification.send_code(user)
        except verification.SendFailed:
            messages.error(request, verification.SEND_FAILED_MESSAGE)
        return redirect("verify_email")
    return render(request, "register.html", {"form": form})


PENDING_KEY = "pending_login"
PENDING_TTL_SECONDS = 15 * 60


def login_view(request):
    """Step 1: username + password. Step 2 (login_verify): a code sent to your email."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        request.session[PENDING_KEY] = {"uid": user.pk, "at": int(time.time()), "next": _next_url(request)}
        if user.email:
            try:
                verification.ensure_code(user)
            except verification.SendFailed:
                messages.error(request, verification.SEND_FAILED_MESSAGE)
        return redirect("login_verify")
    return render(request, "login.html", {"form": form, "next": request.GET.get("next", "")})


def _send(request, user, force=False):
    """Send a code; a recent one (under the resend cooldown) is simply reused."""
    try:
        verification.send_code(user, force=force)
    except verification.SendFailed:
        messages.error(request, verification.SEND_FAILED_MESSAGE)


def _pending_user(request):
    pending = request.session.get(PENDING_KEY)
    if not pending or time.time() - pending.get("at", 0) > PENDING_TTL_SECONDS:
        request.session.pop(PENDING_KEY, None)
        return None, None
    user = get_user_model().objects.filter(pk=pending["uid"], is_active=True).first()
    return user, pending


def login_verify(request):
    user, pending = _pending_user(request)
    if not user:
        if request.content_type == "application/json":
            return JsonResponse({"ok": False, "state": "expired", "message": "Sign in again.", "next": "/login/"})
        messages.info(request, "Sign in again.")
        return redirect("login")

    if request.method == "POST":
        is_json = request.content_type == "application/json"
        code = json_body(request).get("code") if is_json else request.POST.get("code", "")
        state, left = verification.check_code(user, code)
        if state == "verified":
            request.session.pop(PENDING_KEY, None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        if is_json:
            return JsonResponse({"ok": state == "verified", "state": state, "attempts_left": left,
                                 "message": VERIFY_MESSAGES.get(state, ""), "next": pending["next"]})
        if state == "verified":
            return redirect(pending["next"])
        messages.error(request, VERIFY_MESSAGES[state])
        return redirect("login_verify")

    return render(request, "login_verify.html", {
        "needs_email": not user.email,
        "masked": verification.mask_email(user.email) if user.email else "",
        "length": verification.CODE_LENGTH,
        "digits": range(verification.CODE_LENGTH),
        "wait": verification.seconds_until_resend(user),
        "email_is_real": settings.EMAIL_IS_REAL,
    })


@require_POST
def login_resend(request):
    user, _ = _pending_user(request)
    if not user:
        return redirect("login")
    if user.email:
        try:
            wait = verification.send_code(user)
        except verification.SendFailed:
            messages.error(request, verification.SEND_FAILED_MESSAGE)
        else:
            messages.info(request, f"Wait {wait}s before sending another code." if wait else "New code sent.")
    return redirect("login_verify")


@require_POST
def login_add_email(request):
    """Only for accounts made before email was required. Never replaces an existing address."""
    user, _ = _pending_user(request)
    if not user:
        return redirect("login")
    if user.email:
        return redirect("login_verify")
    form = EmailForm(request.POST, user=user)
    if not form.is_valid():
        messages.error(request, form.errors["email"][0])
        return redirect("login_verify")
    form.save()
    _send(request, user, force=True)
    return redirect("login_verify")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")
