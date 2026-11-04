"""Recoverable streaks.

* Solving a public daily challenge before its deadline marks that day.
* Missed yesterday? Solve yesterday's challenge today (the recovery window) and
  the day is marked as "recovered" — no leaderboard points, but the streak lives.
* Streak freezes cover any remaining gap automatically on your next solve.
  You start with one and earn another every 7 days of streak (max 2 banked).
"""

from datetime import timedelta

from .models import MAX_STREAK_FREEZES, StreakDay, utc_today

FREEZE_EVERY_DAYS = 7


def _chain_length(dates, end):
    length, day = 0, end
    while day in dates:
        length += 1
        day -= timedelta(days=1)
    return length


def record_day(user, day, kind=StreakDay.SOLVED):
    """Mark ``day`` as kept for ``user``; fill gaps with freezes if possible."""
    profile = user.profile
    if StreakDay.objects.filter(user=user, date=day).exists():
        return
    previous = StreakDay.objects.filter(user=user, date__lt=day).order_by("-date").first()
    if previous:
        gap = (day - previous.date).days - 1
        if 0 < gap <= profile.streak_freezes:
            for offset in range(1, gap + 1):
                StreakDay.objects.create(user=user, date=previous.date + timedelta(days=offset), kind=StreakDay.FROZEN)
            profile.streak_freezes -= gap
    StreakDay.objects.create(user=user, date=day, kind=kind)

    dates = set(StreakDay.objects.filter(user=user).values_list("date", flat=True))
    latest = max(dates)
    current = _chain_length(dates, latest)
    if day == latest and kind != StreakDay.FROZEN and current % FREEZE_EVERY_DAYS == 0:
        profile.streak_freezes = min(MAX_STREAK_FREEZES, profile.streak_freezes + 1)
    profile.longest_streak = max(profile.longest_streak, current)
    profile.save(update_fields=["streak_freezes", "longest_streak"])


def streak_status(user):
    """Return dict(current, state, freezes, longest, solved_today).

    state: "active" (today done), "pending" (do today to extend),
    "recoverable" (missed days, but freezes / recovery can save it), "broken", "none".
    """
    profile = user.profile
    today = utc_today()
    dates = set(StreakDay.objects.filter(user=user).values_list("date", flat=True))
    info = {"freezes": profile.streak_freezes, "longest": profile.longest_streak, "solved_today": today in dates}
    if not dates:
        return {**info, "current": 0, "state": "none"}
    latest = max(dates)
    chain = _chain_length(dates, latest)
    missed = (today - latest).days - 1  # full days missed between latest and today
    if latest >= today:
        state = "active"
    elif missed <= 0:
        state = "pending"
    elif missed - 1 <= profile.streak_freezes:
        # Yesterday can be recovered by solving its challenge today; freezes cover the rest.
        state = "recoverable"
    else:
        state = "broken"
    return {**info, "current": chain if state != "broken" else 0, "state": state, "missed": max(0, missed)}


def team_streak(team):
    """Consecutive days (ending today or yesterday) on which the team solved the daily challenge in time."""
    days = set(
        team.participations.filter(solved_at__isnull=False, is_practice=False, challenge__team__isnull=True)
        .values_list("challenge__release_date", flat=True)
    )
    today = utc_today()
    end = today if today in days else today - timedelta(days=1)
    return _chain_length(days, end)
