from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import leaderboards, services, streaks
from ..forms import PrivateChallengeForm, TeamForm
from ..models import MAX_TEAM_SIZE, Team, TeamInvite, TeamMembership, TeamMessage, new_invite_code, utc_today
from .helpers import json_body, json_error, safe_next

User = get_user_model()


def _join(user, team):
    """Add ``user`` to ``team``. Returns an error message or None."""
    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team.pk)
        if team.has_member(user):
            return "You're already on this team."
        if user.profile.active_team:
            return f"Leave {user.profile.active_team.name} before joining another team."
        if team.member_count >= MAX_TEAM_SIZE:
            return f"{team.name} is full ({MAX_TEAM_SIZE} members max)."
        TeamMembership.objects.create(team=team, user=user)
        TeamInvite.objects.filter(invited_user=user).delete()
    return None


def teams(request):
    my_team = request.user.profile.active_team if request.user.is_authenticated else None
    public = Team.objects.annotate(members=Count("memberships", filter=Q(memberships__active=True))).filter(members__gt=0)
    query = request.GET.get("q", "").strip()
    if query:
        public = public.filter(name__icontains=query)
    ranking = {row["key"]: row for row in leaderboards.ranked_entries("alltime", "teams", limit=0)}
    team_rows = [{"team": t, "members": t.members, "row": ranking.get(t.slug)} for t in public.order_by("-created_at")[:50]]
    team_rows.sort(key=lambda r: -(r["row"]["score"] if r["row"] else 0))
    return render(request, "teams.html", {
        "my_team": my_team,
        "team_rows": team_rows,
        "form": TeamForm(),
        "query": query,
        "invites": request.user.team_invites.select_related("team", "invited_by") if request.user.is_authenticated else [],
        "max_size": MAX_TEAM_SIZE,
    })


@login_required
@require_POST
def team_create(request):
    if request.user.profile.active_team:
        messages.error(request, "You're already on a team. Leave it first to create a new one.")
        return redirect("teams")
    form = TeamForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            messages.error(request, errors[0])
        return redirect("teams")
    team = form.save(commit=False)
    team.owner = request.user
    team.save()
    TeamMembership.objects.create(team=team, user=request.user)
    messages.success(request, f"Team {team.name} created! Share the invite code with up to {MAX_TEAM_SIZE - 1} friends.")
    return redirect(team)


@login_required
@require_POST
def team_join(request):
    code = request.POST.get("code", "").strip()
    team = Team.objects.filter(invite_code=code).first()
    if not team:
        messages.error(request, "That invite code doesn't match any team.")
        return redirect("teams")
    return _join_and_redirect(request, team)


@login_required
def team_join_link(request, code):
    team = get_object_or_404(Team, invite_code=code)
    if request.method == "POST":
        return _join_and_redirect(request, team)
    return render(request, "team_join.html", {"team": team, "code": code})


def _join_and_redirect(request, team):
    error = _join(request.user, team)
    if error:
        messages.error(request, error)
        return redirect("teams")
    TeamMessage.objects.create(team=team, author=request.user, body="👋 joined the team")
    messages.success(request, f"Welcome to {team.name}!")
    return redirect(team)


def team_detail(request, slug):
    team = get_object_or_404(Team, slug=slug)
    is_member = team.has_member(request.user)
    members = team.active_members
    member_rows = []
    board = leaderboards.ranked_entries("alltime", "all", team=team, limit=0)
    for member in members:
        row = leaderboards.rank_of(board, "player", member.username)
        member_rows.append({"user": member, "streak": streaks.streak_status(member), "row": row, "is_owner": member.pk == team.owner_id})
    member_rows.sort(key=lambda m: -(m["row"]["score"] if m["row"] else 0))
    today = utc_today()
    private = team.private_challenges.order_by("-release_date") if is_member else []
    history = team.participations.filter(solved_at__isnull=False).select_related("challenge").order_by("-solved_at")[:10]
    return render(request, "team_detail.html", {
        "team": team,
        "is_member": is_member,
        "is_owner": request.user.is_authenticated and team.owner_id == request.user.pk,
        "member_rows": member_rows,
        "board": board,
        "streak": streaks.team_streak(team),
        "history": history,
        "private": private,
        "messages_list": team.messages.select_related("author__profile").order_by("-created_at")[:50][::-1] if is_member else [],
        "invite_url": request.build_absolute_uri(f"/teams/join/{team.invite_code}/"),
        "max_size": MAX_TEAM_SIZE,
        "pending_invites": team.invites.select_related("invited_user") if is_member else [],
        "today": today,
        "stats": {
            "solved": team.participations.filter(solved_at__isnull=False).count(),
            "score": round(sum(p.score for p in team.participations.filter(solved_at__isnull=False, is_practice=False)), 1),
        },
    })


@login_required
def team_chat(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if not team.has_member(request.user):
        raise Http404
    if request.method == "POST":
        body = (json_body(request).get("body") or request.POST.get("body") or "").strip()
        if not body:
            return json_error("Message is empty.")
        TeamMessage.objects.create(team=team, author=request.user, body=body[:1000])
    after = request.GET.get("after")
    msgs = team.messages.select_related("author__profile")
    if after and after.isdigit():
        msgs = msgs.filter(pk__gt=int(after))
    else:
        msgs = msgs.order_by("-created_at")[:50][::-1]
    return JsonResponse({"ok": True, "messages": [
        {"id": m.pk, "author": m.author.profile.name, "username": m.author.username, "body": m.body,
         "at": timezone.localtime(m.created_at).strftime("%H:%M"), "mine": m.author_id == request.user.pk}
        for m in msgs
    ]})


@login_required
@require_POST
def team_invite(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if not team.has_member(request.user):
        raise Http404
    username = request.POST.get("username", "").strip()
    invitee = User.objects.filter(username__iexact=username).first()
    if not invitee:
        messages.error(request, f"No player called '{username}'.")
    elif team.has_member(invitee):
        messages.info(request, f"{invitee.username} is already on the team.")
    elif team.is_full:
        messages.error(request, f"The team is full ({MAX_TEAM_SIZE} max).")
    else:
        TeamInvite.objects.get_or_create(team=team, invited_user=invitee, defaults={"invited_by": request.user})
        messages.success(request, f"Invite sent to {invitee.username}.")
    return redirect(team)


@login_required
@require_POST
def invite_respond(request, pk, action):
    invite = get_object_or_404(TeamInvite, pk=pk, invited_user=request.user)
    team = invite.team
    if action == "accept":
        return _join_and_redirect(request, team)
    invite.delete()
    messages.info(request, f"Invite to {team.name} declined.")
    return redirect(safe_next(request, "/dashboard/"))


@login_required
@require_POST
def team_leave(request, slug):
    team = get_object_or_404(Team, slug=slug)
    membership = TeamMembership.objects.filter(team=team, user=request.user, active=True).first()
    if not membership:
        raise Http404
    membership.active = False
    membership.left_at = timezone.now()
    membership.save()
    TeamMessage.objects.create(team=team, author=request.user, body="left the team")
    if team.owner_id == request.user.pk:
        successor = team.memberships.filter(active=True).order_by("joined_at").first()
        team.owner = successor.user if successor else None
        team.save(update_fields=["owner"])
    messages.info(request, f"You left {team.name}.")
    return redirect("teams")


@login_required
@require_POST
def team_kick(request, slug, username):
    team = get_object_or_404(Team, slug=slug, owner=request.user)
    membership = get_object_or_404(TeamMembership, team=team, user__username=username, active=True)
    if membership.user_id == request.user.pk:
        messages.error(request, "Use 'Leave team' to remove yourself.")
        return redirect(team)
    membership.active = False
    membership.left_at = timezone.now()
    membership.save()
    messages.info(request, f"{username} was removed from the team.")
    return redirect(team)


@login_required
@require_POST
def team_regenerate_code(request, slug):
    team = get_object_or_404(Team, slug=slug, owner=request.user)
    team.invite_code = new_invite_code()
    team.save(update_fields=["invite_code"])
    messages.success(request, "New invite code generated — old links no longer work.")
    return redirect(team)


@login_required
def team_private_challenge(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if not team.has_member(request.user):
        raise Http404
    form = PrivateChallengeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        base = f"{team.slug}-{data['release_date'].isoformat()}-{data['function_name'].replace('_', '-')}"
        try:
            challenge = services.create_challenge(
                title=data["title"], slug=base[:110], description=data["description"],
                difficulty=data["difficulty"], release_date=data["release_date"],
                function_name=data["function_name"], params=data["params"],
                reference_python=data["reference_python"], examples=data["examples"],
                hidden=data["hidden"], hints=data["hints"], team=team, created_by=request.user,
            )
        except ValueError as exc:
            form.add_error("reference_python", str(exc))
        except IntegrityError:
            form.add_error("function_name", "Your team already has a challenge with this function on that date.")
        else:
            TeamMessage.objects.create(team=team, author=request.user, body=f"🧩 created a private challenge: {challenge.title} ({challenge.release_date})")
            messages.success(request, "Private challenge created.")
            return redirect(team)
    return render(request, "team_challenge_form.html", {"team": team, "form": form})
