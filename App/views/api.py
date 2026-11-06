"""Token-authenticated JSON API used by the IDE plugins and the CLI.

Authenticate with the header ``Authorization: Token <your token>`` (Settings → Integrations).
"""

from functools import wraps

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .. import runner, services, streaks
from ..models import Challenge, Profile, utc_today
from .helpers import json_body, json_error, json_errors, serialize_entry, serialize_run


def token_required(view):
    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        profile = None
        if scheme.lower() in ("token", "bearer") and token.strip():
            profile = Profile.objects.select_related("user").filter(api_token=token.strip()).first()
        if not profile or not profile.user.is_active:
            return json_error("Invalid or missing API token. Generate one in Settings → Integrations.", status=401)
        request.user = profile.user
        return view(request, *args, **kwargs)

    return wrapper


def _challenge_payload(challenge, user):
    entry = services.find_participation(user, challenge)
    return {
        "slug": challenge.slug,
        "title": challenge.title,
        "difficulty": challenge.difficulty,
        "release_date": challenge.release_date.isoformat(),
        "opens_at": challenge.opens_at.isoformat(),
        "closes_at": challenge.closes_at.isoformat(),
        "description": challenge.description,
        "constraints": challenge.constraints,
        "function": {"python": challenge.function_name, "javascript": challenge.js_function_name},
        "params": challenge.param_list,
        "starter_code": {lang: challenge.starter_code(lang) for lang in runner.available_languages()},
        "examples": [{"args": t.args, "expected": t.expected} for t in challenge.tests.filter(is_example=True)],
        "url": challenge.get_absolute_url(),
        "entry": serialize_entry(entry) if entry else None,
    }


@token_required
@require_GET
def api_me(request):
    user = request.user
    team = user.profile.active_team
    return JsonResponse({
        "ok": True,
        "username": user.username,
        "name": user.profile.name,
        "team": {"name": team.name, "slug": team.slug} if team else None,
        "streak": streaks.streak_status(user),
        "stats": services.user_stats(user),
        "languages": runner.available_languages(),
    })


@token_required
@require_GET
def api_today(request):
    return JsonResponse({"ok": True, "challenge": _challenge_payload(services.todays_challenge(), request.user)})


@token_required
@require_GET
def api_challenges(request):
    """Recent public problems (today first), with the caller's result on each."""
    services.todays_challenge()
    today = utc_today()
    challenges = list(Challenge.objects.filter(team__isnull=True, release_date__lte=today).order_by("-release_date")[:30])
    entries = {e.challenge_id: e for e in services.user_entries(request.user).filter(challenge__in=challenges)}
    return JsonResponse({"ok": True, "challenges": [
        {
            "slug": c.slug, "title": c.title, "difficulty": c.difficulty,
            "release_date": c.release_date.isoformat(), "is_today": c.release_date == today,
            "solved": bool(entries.get(c.pk) and entries[c.pk].solved),
            "score": entries[c.pk].score if c.pk in entries and entries[c.pk].solved else None,
        }
        for c in challenges
    ]})


@token_required
@require_GET
def api_challenge(request, slug):
    challenge = get_object_or_404(Challenge, slug=slug)
    if not challenge.is_visible_to(request.user):
        return json_error("Challenge not available.", status=404)
    return JsonResponse({"ok": True, "challenge": _challenge_payload(challenge, request.user)})


def _resolve(request, data):
    slug = data.get("challenge")
    challenge = get_object_or_404(Challenge, slug=slug) if slug else services.todays_challenge()
    if not challenge.is_visible_to(request.user):
        return None
    return challenge


@token_required
@require_POST
@json_errors
def api_run(request):
    data = json_body(request)
    challenge = _resolve(request, data)
    if not challenge:
        return json_error("Challenge not available.", status=404)
    try:
        result = services.run_examples(request.user, challenge, data.get("code", ""), data.get("language", "python"))
    except services.ChallengeError as exc:
        return json_error(str(exc))
    return JsonResponse({"ok": True, "result": serialize_run(result)})


@token_required
@require_POST
@json_errors
def api_submit(request):
    data = json_body(request)
    challenge = _resolve(request, data)
    if not challenge:
        return json_error("Challenge not available.", status=404)
    if data.get("mode") in ("solo", "team"):
        try:
            services.start_participation(request.user, challenge, data["mode"])
        except services.ChallengeError as exc:
            return json_error(str(exc))
    try:
        submission, result, entry = services.submit(
            request.user, challenge, data.get("code", ""), data.get("language", "python"), via_api=True
        )
    except services.ChallengeError as exc:
        return json_error(str(exc))
    payload = serialize_run(result)
    for case, test in zip(payload["cases"], challenge.tests.all()):
        if not test.is_example:
            case.update(got=None, expected=None, stdout="")
    return JsonResponse({"ok": True, "submission_id": submission.pk, "result": payload, "entry": serialize_entry(entry)})
