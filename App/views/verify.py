from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .. import verification
from .helpers import json_body

MESSAGES = {
    "wrong": "That code isn't right.",
    "expired": "That code expired. Send a new one.",
    "locked": "Too many tries. Send a new code.",
    "missing": "Send yourself a code first.",
}


class ChangeEmailForm(forms.Form):
    email = forms.EmailField()


@login_required
def verify_email(request):
    user = request.user
    if user.profile.email_verified:
        return redirect("dashboard")

    if request.method == "POST":
        code = json_body(request).get("code") if request.content_type == "application/json" else request.POST.get("code", "")
        state, left = verification.check_code(user, code)
        if request.content_type == "application/json":
            return JsonResponse({"ok": state == "verified", "state": state, "attempts_left": left,
                                 "message": MESSAGES.get(state, ""), "next": "/dashboard/"})
        if state == "verified":
            messages.success(request, "Email verified.")
            return redirect("dashboard")
        messages.error(request, MESSAGES[state])
        return redirect("verify_email")

    if not user.email_codes.filter(used=False).exists():
        verification.send_code(user)
    return render(request, "verify.html", {
        "masked": verification.mask_email(user.email),
        "length": verification.CODE_LENGTH,
        "digits": range(verification.CODE_LENGTH),
        "wait": verification.seconds_until_resend(user),
        "email_form": ChangeEmailForm(initial={"email": user.email}),
    })


@login_required
@require_POST
def resend_code(request):
    wait = verification.send_code(request.user)
    if wait:
        messages.info(request, f"Wait {wait}s before sending another code.")
    else:
        messages.success(request, "New code sent.")
    return redirect("verify_email")


@login_required
@require_POST
def change_email(request):
    form = ChangeEmailForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid email.")
        return redirect("verify_email")
    email = form.cleaned_data["email"]
    taken = get_user_model().objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists()
    if taken:
        messages.error(request, "That email is already in use.")
        return redirect("verify_email")
    request.user.email = email
    request.user.save(update_fields=["email"])
    verification.send_code(request.user, force=True)
    messages.success(request, "Code sent to your new address.")
    return redirect("verify_email")
