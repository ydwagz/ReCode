from django.shortcuts import redirect

# Paths an unverified (but logged-in) account may still reach.
OPEN_PREFIXES = ("/verify/", "/logout/", "/static/", "/admin/", "/api/")


class EmailVerificationMiddleware:
    """Send logged-in accounts with an unconfirmed e-mail to /verify/ before they can play."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            user.is_authenticated
            and not user.is_staff
            and not request.path.startswith(OPEN_PREFIXES)
            and not user.profile.email_verified
        ):
            if request.headers.get("Content-Type", "").startswith("application/json"):
                from django.http import JsonResponse

                return JsonResponse({"ok": False, "error": "Verify your email first.", "verify_url": "/verify/"}, status=403)
            return redirect("verify_email")
        return self.get_response(request)
