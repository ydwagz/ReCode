from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .. import leaderboards, services, streaks, verification
from ..forms import AccountForm, PreferencesForm, WebhookForm
from ..models import Challenge, StreakDay, Submission, new_token, utc_today

User = get_user_model()


def home(request):
    challenge = services.todays_challenge()
    solvers = challenge.participations.filter(solved_at__isnull=False).count()
    top = leaderboards.ranked_entries("daily", limit=5)
    return render(request, "home.html", {"challenge": challenge, "solvers": solvers, "top": top})


@login_required
def dashboard(request):
    user = request.user
    challenge = services.todays_challenge()
    entry = services.find_participation(user, challenge)
    team = user.profile.active_team
    daily = leaderboards.ranked_entries("daily", limit=0)
    me = leaderboards.rank_of(daily, "player", user.username)
    team_row = leaderboards.rank_of(daily, "team", team.slug) if team else None
    recent = services.user_entries(user).filter(solved_at__isnull=False).select_related("challenge", "team").order_by("-solved_at")[:6]
    calendar = _streak_calendar(user)
    return render(request, "dashboard.html", {
        "challenge": challenge,
        "entry": entry,
        "team": team,
        "team_streak": streaks.team_streak(team) if team else 0,
        "streak": streaks.streak_status(user),
        "my_rank": (team_row if entry and entry.team_id else me),
        "field_size": len(daily),
        "recent": recent,
        "upcoming": services.upcoming_days(3),
        "invites": user.team_invites.select_related("team", "invited_by"),
        "calendar": calendar,
        "yesterday": _yesterday_recovery(user),
        "stats": services.user_stats(user),
    })


def _streak_calendar(user, days=28):
    today = utc_today()
    marks = dict(StreakDay.objects.filter(user=user, date__gt=today - timedelta(days=days)).values_list("date", "kind"))
    return [{"date": today - timedelta(days=i), "kind": marks.get(today - timedelta(days=i))} for i in range(days - 1, -1, -1)]


def _yesterday_recovery(user):
    """Yesterday's challenge if the user missed it and can still recover their streak today."""
    yesterday = utc_today() - timedelta(days=1)
    if StreakDay.objects.filter(user=user, date=yesterday).exists():
        return None
    if not StreakDay.objects.filter(user=user).exists():
        return None
    return Challenge.objects.filter(release_date=yesterday, team__isnull=True).first()


def _profile_context(user, viewer):
    entries = (
        services.user_entries(user).filter(solved_at__isnull=False).select_related("challenge", "team").order_by("-solved_at")
    )
    solutions = Submission.objects.filter(user=user, status="accepted").select_related("participation__challenge").order_by("-created_at")
    if viewer != user:
        # Other people only see solutions to challenges that have closed.
        solutions = [s for s in solutions[:60] if s.participation.challenge.is_closed and not s.participation.challenge.team_id][:20]
    else:
        solutions = solutions[:20]
    return {
        "subject": user,
        "is_me": viewer == user,
        "stats": services.user_stats(user),
        "streak": streaks.streak_status(user),
        "badges": services.badges_for(user),
        "entries": entries[:15],
        "solutions": solutions,
        "memberships": user.memberships.select_related("team").order_by("-joined_at"),
        "calendar": _streak_calendar(user, days=84),
    }


@login_required
def profile(request):
    return render(request, "profile.html", _profile_context(request.user, request.user))


def public_profile(request, username):
    subject = get_object_or_404(User.objects.select_related("profile"), username=username)
    if subject != request.user and not subject.profile.public_profile:
        raise Http404("This profile is private")
    return render(request, "profile.html", _profile_context(subject, request.user))


@login_required
def settings_view(request):
    profile = request.user.profile
    section = request.POST.get("section", "")
    forms = {
        "account": AccountForm(request.POST if section == "account" else None, instance=profile, prefix="account"),
        "preferences": PreferencesForm(request.POST if section == "preferences" else None, instance=profile, prefix="prefs"),
        "webhook": WebhookForm(request.POST if section == "webhook" else None, instance=profile, prefix="hook"),
        "password": PasswordChangeForm(request.user, request.POST if section == "password" else None, prefix="pw"),
    }
    if request.method == "POST":
        if section == "token":
            profile.api_token = new_token()
            profile.save(update_fields=["api_token"])
            messages.success(request, "New plugin token generated. Update it in your IDE.")
            return redirect("/settings/#integrations")
        form = forms.get(section)
        if form and form.is_valid():
            saved = form.save()
            if section == "password":
                update_session_auth_hash(request, saved)
            if section == "account" and not profile.email_verified:
                verification.send_code(request.user, force=True)
                return redirect("verify_email")
            messages.success(request, "Saved.")
            return redirect(f"/settings/#{section}")
        messages.error(request, "Please fix the errors below.")
    return render(request, "settings.html", {
        **forms,
        "token": profile.api_token,
        "api_base": request.build_absolute_uri("/api/v1/"),
    })
