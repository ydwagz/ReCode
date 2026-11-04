from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.timesince import timesince

from .. import leaderboards, runner, services
from ..models import Challenge, Comment, Participation, utc_today


def _filters(request):
    period = request.GET.get("period", "daily")
    scope = request.GET.get("scope", "all")
    language = request.GET.get("language", "")
    return (
        period if period in leaderboards.PERIODS else "daily",
        scope if scope in leaderboards.SCOPES else "all",
        language if language in dict(Participation._meta.get_field("language").choices) else "",
        request.GET.get("q", "").strip()[:40],
    )


def leaderboard(request):
    services.todays_challenge()
    period, scope, language, search = _filters(request)
    rows = leaderboards.ranked_entries(period, scope, language, search)
    me = None
    if request.user.is_authenticated:
        everyone = leaderboards.ranked_entries(period, "all", language, "", limit=0)
        me = leaderboards.rank_of(everyone, "player", request.user.username)
    return render(request, "leaderboard.html", {
        "rows": rows,
        "period": period,
        "scope": scope,
        "language": language,
        "search": search,
        "periods": leaderboards.PERIODS,
        "scopes": leaderboards.SCOPES,
        "languages": runner.available_languages(),
        "me": me,
        "challenge": services.todays_challenge(),
    })


def leaderboard_data(request):
    period, scope, language, search = _filters(request)
    rows = leaderboards.ranked_entries(period, scope, language, search)
    return JsonResponse({"ok": True, "updated": timezone.now().isoformat(), "rows": rows})


def community(request):
    today = utc_today()
    challenge = services.todays_challenge()
    activity = []
    for entry in Participation.objects.filter(solved_at__isnull=False, is_practice=False, challenge__team__isnull=True).select_related(
        "user__profile", "team", "challenge"
    ).order_by("-solved_at")[:15]:
        if not entry.team_id and not entry.user.profile.show_on_leaderboard:
            continue
        activity.append({
            "kind": "solve",
            "who": entry.owner_name,
            "url": entry.team.get_absolute_url() if entry.team_id else f"/u/{entry.user.username}/",
            "is_team": entry.is_team,
            "challenge": entry.challenge,
            "score": entry.score,
            "seconds": entry.solve_seconds,
            "ago": timesince(entry.solved_at),
            "at": entry.solved_at,
        })
    for comment in Comment.objects.filter(challenge__team__isnull=True).select_related("author__profile", "challenge").order_by("-created_at")[:10]:
        activity.append({
            "kind": "comment",
            "who": comment.author.profile.name,
            "url": f"/u/{comment.author.username}/",
            "challenge": comment.challenge,
            "body": comment.body,
            "comment_id": comment.pk,
            "ago": timesince(comment.created_at),
            "at": comment.created_at,
        })
    activity.sort(key=lambda a: a["at"], reverse=True)

    threads = (
        Challenge.objects.filter(team__isnull=True, release_date__lte=today)
        .annotate(n_comments=Count("comments", distinct=True))
        .order_by("-release_date")[:10]
    )
    galleries = (
        Challenge.objects.filter(team__isnull=True, release_date__lt=today)
        .annotate(n_shared=Count("participations__submissions", filter=Q(participations__submissions__shared=True)))
        .order_by("-release_date")[:6]
    )
    hot = Comment.objects.filter(challenge__team__isnull=True, parent__isnull=True).select_related("author__profile", "challenge").order_by("-score", "-created_at")[:5]
    return render(request, "community.html", {
        "challenge": challenge,
        "activity": activity[:20],
        "threads": threads,
        "galleries": galleries,
        "hot": hot,
    })
