from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, OuterRef, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .. import runner, services
from ..forms import CommentForm
from ..models import Challenge, Comment, CommentVote, Participation, SolutionLike, Submission, utc_today
from .helpers import json_body, json_error, json_errors, safe_next, serialize_entry, serialize_run


def _visible_challenge(request, slug):
    challenge = get_object_or_404(Challenge.objects.select_related("team"), slug=slug)
    if not challenge.is_visible_to(request.user):
        raise Http404("Challenge not available")
    return challenge


def today_redirect(request):
    return redirect(services.todays_challenge())


def challenge_list(request):
    services.todays_challenge()
    today = utc_today()
    challenges = Challenge.objects.filter(team__isnull=True, release_date__lte=today).annotate(
        solvers=Count("participations", filter=Q(participations__solved_at__isnull=False))
    )
    difficulty = request.GET.get("difficulty", "")
    if difficulty:
        challenges = challenges.filter(difficulty=difficulty)
    status = {}
    if request.user.is_authenticated:
        for entry in services.user_entries(request.user).filter(challenge__in=challenges):
            status[entry.challenge_id] = entry
    rows = [{"challenge": c, "entry": status.get(c.pk)} for c in challenges[:120]]
    return render(request, "challenge_list.html", {"rows": rows, "difficulty": difficulty, "today": today})


def challenge_detail(request, slug):
    challenge = _visible_challenge(request, slug)
    user = request.user
    entry = services.find_participation(user, challenge) if user.is_authenticated else None
    team = user.profile.active_team if user.is_authenticated else None
    if challenge.team_id:
        team = challenge.team
    history = entry.submissions.select_related("user__profile")[:20] if entry else []
    languages = runner.available_languages()
    default_language = user.profile.default_language if user.is_authenticated else "python"
    if default_language not in languages:
        default_language = "python"
    last_code = {}
    if entry:
        for sub in entry.submissions.filter(user=user).order_by("-created_at"):
            last_code.setdefault(sub.language, sub.code)
    starter = {lang: last_code.get(lang) or challenge.starter_code(lang) for lang in languages}
    hints = services.revealed_hints(entry)
    total_hints = challenge.hints.count()
    next_hint = challenge.hints.exclude(pk__in=[h.pk for h in hints]).first()
    context = {
        "challenge": challenge,
        "examples": challenge.tests.filter(is_example=True),
        "test_count": challenge.tests.count(),
        "entry": entry,
        "team": team,
        "history": history,
        "languages": languages,
        "default_language": default_language,
        "starter": starter,
        "hints": hints,
        "total_hints": total_hints,
        "next_hint": next_hint,
        "comment_count": challenge.comments.count(),
        "is_today": challenge.release_date == utc_today(),
        "recoverable": challenge.release_date == utc_today() - timedelta(days=1) and not challenge.team_id,
    }
    return render(request, "challenge.html", context)


@login_required
@require_POST
def challenge_start(request, slug):
    challenge = _visible_challenge(request, slug)
    mode = request.POST.get("mode", "solo")
    try:
        services.start_participation(request.user, challenge, mode)
    except services.ChallengeError as exc:
        messages.error(request, str(exc))
    return redirect(challenge)


@login_required
@require_POST
@json_errors
def challenge_run(request, slug):
    challenge = _visible_challenge(request, slug)
    data = json_body(request)
    try:
        result = services.run_examples(request.user, challenge, data.get("code", ""), data.get("language", "python"))
    except services.ChallengeError as exc:
        return json_error(str(exc), status=429 if "wait" in str(exc).lower() or "limit" in str(exc).lower() else 400)
    return JsonResponse({"ok": True, "result": serialize_run(result)})


@login_required
@require_POST
@json_errors
def challenge_submit(request, slug):
    challenge = _visible_challenge(request, slug)
    data = json_body(request)
    try:
        submission, result, entry = services.submit(request.user, challenge, data.get("code", ""), data.get("language", "python"))
    except services.ChallengeError as exc:
        return json_error(str(exc), status=429 if "limit" in str(exc).lower() or "slow down" in str(exc).lower() else 400)
    payload = serialize_run(result)
    examples = list(challenge.tests.values_list("is_example", flat=True))
    for case, is_example in zip(payload["cases"], examples):
        if not is_example:  # never leak hidden test data
            case.update(got=None, expected=None, stdout="")
    return JsonResponse({"ok": True, "submission_id": submission.pk, "result": payload, "entry": serialize_entry(entry)})


@login_required
@require_POST
@json_errors
def challenge_hint(request, slug):
    challenge = _visible_challenge(request, slug)
    try:
        hint = services.reveal_hint(request.user, challenge)
    except services.ChallengeError as exc:
        return json_error(str(exc))
    remaining = challenge.hints.filter(order__gt=hint.order)
    upcoming = remaining.first()
    return JsonResponse({
        "ok": True,
        "hint": {"order": hint.order, "text": hint.text, "cost": hint.cost},
        "remaining": remaining.count(),
        "next_cost": upcoming.cost if upcoming else None,
    })


@login_required
def challenge_progress(request, slug):
    """Live progress for the viewer's entry (team members, attempts, status)."""
    challenge = _visible_challenge(request, slug)
    entry = services.find_participation(request.user, challenge)
    if not entry:
        return JsonResponse({"ok": True, "entry": None, "members": []})
    members = []
    people = entry.team.active_members if entry.team_id else [entry.user]
    for person in people:
        subs = entry.submissions.filter(user=person)
        last = subs.first()
        members.append({
            "name": person.profile.name,
            "username": person.username,
            "submissions": subs.count(),
            "last_status": last.status if last else None,
            "last_at": last.created_at.isoformat() if last else None,
            "solved": subs.filter(status="accepted").exists(),
        })
    return JsonResponse({"ok": True, "entry": serialize_entry(entry), "members": members})


def challenge_discussion(request, slug):
    challenge = _visible_challenge(request, slug)
    form = CommentForm(request.POST or None)
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"/login/?next={request.path}")
        if form.is_valid():
            comment = form.save(commit=False)
            comment.challenge = challenge
            comment.author = request.user
            parent_id = form.cleaned_data.get("parent")
            if parent_id:
                comment.parent = get_object_or_404(Comment, pk=parent_id, challenge=challenge, parent__isnull=True)
            comment.save()
            return redirect(f"{request.path}#c{comment.pk}")
    comments = challenge.comments.filter(parent__isnull=True).select_related("author__profile").prefetch_related("replies__author__profile")
    my_votes = {}
    if request.user.is_authenticated:
        my_votes = dict(CommentVote.objects.filter(user=request.user, comment__challenge=challenge).values_list("comment_id", "value"))
    return render(request, "discussion.html", {"challenge": challenge, "comments": comments, "form": form, "my_votes": my_votes})


@login_required
@require_POST
def comment_vote(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if not comment.challenge.is_visible_to(request.user):
        raise Http404
    value = 1 if json_body(request).get("value", request.POST.get("value")) in (1, "1", "up") else -1
    vote = CommentVote.objects.filter(comment=comment, user=request.user).first()
    if vote and vote.value == value:
        vote.delete()  # clicking the same arrow again removes the vote
        value = 0
    elif vote:
        vote.value = value
        vote.save()
    else:
        CommentVote.objects.create(comment=comment, user=request.user, value=value)
    comment.score = sum(comment.votes.values_list("value", flat=True))
    comment.save(update_fields=["score"])
    return JsonResponse({"ok": True, "score": comment.score, "mine": value})


def solutions(request, slug):
    challenge = _visible_challenge(request, slug)
    if not challenge.is_closed:
        return render(request, "solutions.html", {"challenge": challenge, "locked": True})
    subs = (
        Submission.objects.filter(participation__challenge=challenge, status="accepted", shared=True, flagged=False)
        .select_related("user__profile", "participation__team")
        .annotate(like_count=Count("likes"))
    )
    if request.user.is_authenticated:
        subs = subs.annotate(liked=Exists(SolutionLike.objects.filter(submission=OuterRef("pk"), user=request.user)))
    language = request.GET.get("language", "")
    if language:
        subs = subs.filter(language=language)
    top = Participation.objects.filter(challenge=challenge, solved_at__isnull=False, is_practice=False).order_by("-score")[:1]
    return render(request, "solutions.html", {
        "challenge": challenge,
        "submissions": subs.order_by("-like_count", "created_at")[:50],
        "language": language,
        "reference": challenge.reference_python,
        "top": top[0] if top else None,
    })


@login_required
@require_POST
def submission_share(request, pk):
    submission = get_object_or_404(Submission, pk=pk, user=request.user, status="accepted")
    submission.shared = not submission.shared
    submission.save(update_fields=["shared"])
    if submission.shared:
        messages.success(request, "Shared! It will appear in the solution gallery once the challenge closes.")
    else:
        messages.info(request, "Your solution is no longer shared.")
    return redirect(safe_next(request, submission.participation.challenge.get_absolute_url()))


@login_required
@require_POST
def solution_like(request, pk):
    submission = get_object_or_404(Submission, pk=pk, shared=True, status="accepted")
    if not submission.participation.challenge.is_closed:
        raise Http404
    like, created = SolutionLike.objects.get_or_create(submission=submission, user=request.user)
    if not created:
        like.delete()
    return JsonResponse({"ok": True, "liked": created, "count": submission.likes.count()})
