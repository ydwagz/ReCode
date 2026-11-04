"""Leaderboard queries. Ranking: total score (desc), then total solve time (asc)."""

from datetime import timedelta

from django.db.models import Q

from .models import Participation, utc_today

PERIODS = {"daily": "Today", "weekly": "This week", "alltime": "All time"}
SCOPES = {"all": "Everyone", "players": "Solo players", "teams": "Teams"}


def period_range(period):
    today = utc_today()
    if period == "daily":
        return today, today
    if period == "weekly":
        start = today - timedelta(days=today.weekday())  # Monday, UTC
        return start, today
    return None, today


def ranked_entries(period="daily", scope="all", language="", search="", team=None, limit=100):
    """Aggregated rows: dict(kind, name, key, score, solved, seconds, rank)."""
    start, end = period_range(period)
    qs = Participation.objects.filter(solved_at__isnull=False, is_practice=False, challenge__release_date__lte=end)
    if team is not None:
        # Private group leaderboard: the team's daily/private entries + its members' solo entries.
        member_ids = [m.pk for m in team.active_members]
        qs = qs.filter(Q(team=team) | Q(user_id__in=member_ids, team__isnull=True))
        qs = qs.filter(Q(challenge__team__isnull=True) | Q(challenge__team=team))
    else:
        qs = qs.filter(challenge__team__isnull=True)
        qs = qs.filter(Q(team__isnull=False) | Q(user__profile__show_on_leaderboard=True))
    if start:
        qs = qs.filter(challenge__release_date__gte=start)
    if language:
        qs = qs.filter(language=language)
    if scope == "players":
        qs = qs.filter(team__isnull=True)
    elif scope == "teams":
        qs = qs.filter(team__isnull=False)
    if search:
        qs = qs.filter(Q(team__name__icontains=search) | Q(user__username__icontains=search) | Q(user__profile__display_name__icontains=search))

    rows = {}
    for entry in qs.select_related("user__profile", "team"):
        if entry.team_id:
            key, row = ("team", entry.team.slug), {"kind": "team", "name": entry.team.name, "key": entry.team.slug}
        else:
            key, row = ("player", entry.user.username), {"kind": "player", "name": entry.user.profile.name, "key": entry.user.username}
        agg = rows.setdefault(key, {**row, "score": 0.0, "solved": 0, "seconds": 0, "language": entry.language})
        agg["score"] += entry.score
        agg["solved"] += 1
        agg["seconds"] += entry.solve_seconds or 0
    rows = list(rows.values())
    for row in rows:
        row["score"] = round(row["score"], 2)
    rows.sort(key=lambda r: (-r["score"], r["seconds"], r["name"].lower()))
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows[:limit] if limit else rows


def rank_of(rows, kind, key):
    for row in rows:
        if row["kind"] == kind and row["key"] == key:
            return row
    return None
