import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from App import scoring, services
from App.models import (
    Challenge,
    Comment,
    Participation,
    StreakDay,
    Submission,
    Team,
    TeamMembership,
    TeamMessage,
    utc_today,
)

User = get_user_model()

NAMES = [
    "luca", "nia", "tamara", "dave", "george", "matthew", "emma", "oliver", "sophia", "noah",
    "mia", "ethan", "isabella", "james", "amelia", "lily", "henry", "grace", "dylan", "victoria",
]
TEAMS = {
    "Null Pointers": ["luca", "nia", "tamara", "dave"],
    "Off By One": ["emma", "oliver", "sophia"],
    "Stack Smashers": ["mia", "ethan", "isabella", "james", "amelia"],
}
COMMENTS = [
    "Anyone else try a brute force first? Worked for the examples but the perf test humbled me 😅",
    "Tip: read the constraints before you start, they basically tell you the complexity you need.",
    "Took me three attempts because I forgot the empty input case. Classic.",
    "Is it just me or was today's one easier than yesterday's?",
    "Loved this one. Clean little problem.",
]
DEMO_PASSWORD = "recode-demo-123"


class Command(BaseCommand):
    help = f"Create demo players, teams and results (password for every demo user: {DEMO_PASSWORD})."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14)

    @transaction.atomic
    def handle(self, *args, days, **options):
        rng = random.Random(42)
        today = utc_today()
        for offset in range(days, -1, -1):
            services.ensure_daily_challenge(today - timedelta(days=offset))

        users = {}
        for name in NAMES:
            user, created = User.objects.get_or_create(username=name)
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                user.profile.display_name = name.capitalize()
                user.profile.default_language = rng.choice(["python", "python", "javascript"])
                user.profile.save()
            users[name] = user

        team_of = {}
        for team_name, members in TEAMS.items():
            team, _ = Team.objects.get_or_create(name=team_name, defaults={"owner": users[members[0]]})
            for member in members:
                TeamMembership.objects.get_or_create(team=team, user=users[member], defaults={"active": True})
                team_of[member] = team
            if not team.messages.exists():
                for member, body in zip(members, ["gm team 👋", "today's one looks spicy", "I'll take the edge cases"]):
                    TeamMessage.objects.create(team=team, author=users[member], body=body)

        skill = {name: rng.uniform(0.45, 0.95) for name in NAMES}
        challenges = Challenge.objects.filter(team__isnull=True, release_date__gte=today - timedelta(days=days), release_date__lte=today)
        for challenge in challenges:
            is_today = challenge.release_date == today
            teams_done = set()
            for name, user in users.items():
                if rng.random() > skill[name] + (0.0 if not is_today else -0.3):
                    continue
                team = team_of.get(name) if rng.random() < 0.5 else None
                if team and team.pk in teams_done:
                    continue
                if team:
                    teams_done.add(team.pk)
                    entry, created = Participation.objects.get_or_create(challenge=challenge, team=team)
                else:
                    if Participation.objects.filter(challenge=challenge, team__isnull=True, user=user).exists():
                        continue
                    entry, created = Participation.objects.get_or_create(challenge=challenge, user=user, team=None)
                if not created:
                    continue
                start = challenge.opens_at + timedelta(minutes=rng.randint(10, 600))
                solve_seconds = int(rng.expovariate(1 / (900 / skill[name])))
                fails = max(0, int(rng.expovariate(skill[name] * 2)))
                language = user.profile.default_language
                latest = timezone.now() - timedelta(minutes=1)
                if start + timedelta(seconds=solve_seconds) > latest:
                    start = max(challenge.opens_at, latest - timedelta(seconds=solve_seconds))
                    solve_seconds = int((latest - start).total_seconds())
                breakdown = scoring.score(
                    solved=True, failed_attempts=fails, solve_seconds=solve_seconds,
                    runtime_ms=rng.uniform(1, 4), reference_runtime_ms=1.5,
                )
                entry.started_at = start
                entry.solved_at = start + timedelta(seconds=solve_seconds)
                entry.failed_attempts = fails
                entry.language = language
                entry.correctness_points = breakdown.correctness
                entry.attempt_points = breakdown.attempts
                entry.speed_points = breakdown.speed
                entry.efficiency_points = breakdown.efficiency
                entry.score = breakdown.total
                entry.save()
                code = challenge.reference_javascript if language == "javascript" else challenge.reference_python
                Submission.objects.filter(participation=entry).delete()
                sub = Submission.objects.create(
                    participation=entry, user=user, language=language, code=code, status="accepted",
                    passed_count=challenge.tests.count(), total_count=challenge.tests.count(),
                    runtime_ms=2.0, shared=rng.random() < 0.3,
                )
                Submission.objects.filter(pk=sub.pk).update(created_at=entry.solved_at)
                for member in (team.active_members if team else [user]):
                    StreakDay.objects.get_or_create(user=member, date=challenge.release_date, defaults={"kind": StreakDay.SOLVED})

            if not challenge.comments.exists():
                for body in rng.sample(COMMENTS, 2):
                    author = users[rng.choice(NAMES)]
                    comment = Comment.objects.create(challenge=challenge, author=author, body=body, score=rng.randint(0, 12))
                    if rng.random() < 0.5:
                        Comment.objects.create(challenge=challenge, author=users[rng.choice(NAMES)], parent=comment, body="Same here!")

        for user in users.values():
            dates = set(StreakDay.objects.filter(user=user).values_list("date", flat=True))
            best = run = 0
            day = min(dates) if dates else today
            while day <= today:
                run = run + 1 if day in dates else 0
                best = max(best, run)
                day += timedelta(days=1)
            user.profile.longest_streak = best
            user.profile.save(update_fields=["longest_streak"])

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready: {len(users)} players, {len(TEAMS)} teams. Log in as any of them with password '{DEMO_PASSWORD}'."
        ))
