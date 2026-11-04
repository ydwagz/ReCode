"""Business logic shared by the web views and the plugin API."""

import json
import logging
import threading
import urllib.request
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from . import anticheat, problem_bank, runner, scoring, streaks
from .models import (
    Challenge,
    Hint,
    HintUsage,
    Participation,
    StreakDay,
    Submission,
    TestCase,
    utc_today,
)

log = logging.getLogger(__name__)

FREE_HINTS = 1
HINT_COST = 3


class ChallengeError(Exception):
    """A user-facing error (bad request, not allowed, rate limited...)."""


# ---------------------------------------------------------------- challenges

@transaction.atomic
def create_challenge(*, title, slug, description, release_date, function_name, params, reference_python,
                     examples, hidden, performance=(), constraints="", difficulty="easy",
                     reference_javascript="", hints=(), explanation="", team=None, created_by=None):
    """Create a challenge and its tests. Expected outputs come from the reference solution."""
    all_args = list(examples) + list(hidden) + list(performance)
    expected = runner.compute_expected(reference_python, function_name, all_args)
    challenge = Challenge.objects.create(
        title=title, slug=slug, description=description, constraints=constraints, difficulty=difficulty,
        release_date=release_date, function_name=function_name, params=params,
        reference_python=reference_python, reference_javascript=reference_javascript,
        explanation=explanation, team=team, created_by=created_by,
    )
    kinds = [(a, True, False) for a in examples] + [(a, False, False) for a in hidden] + [(a, False, True) for a in performance]
    TestCase.objects.bulk_create(
        TestCase(challenge=challenge, args=args, expected=exp, is_example=ex, is_performance=perf, order=i)
        for i, ((args, ex, perf), exp) in enumerate(zip(kinds, expected))
    )
    Hint.objects.bulk_create(
        Hint(challenge=challenge, order=i + 1, text=text, cost=0 if i < FREE_HINTS else HINT_COST)
        for i, text in enumerate(hints)
    )
    return challenge


def ensure_daily_challenge(day):
    """Return the public challenge for ``day``, generating one from the problem bank if needed."""
    existing = Challenge.objects.filter(release_date=day, team__isnull=True).first()
    if existing:
        return existing
    problem = problem_bank.problem_for_date(day)
    try:
        return create_challenge(
            title=problem["title"],
            slug=f"{problem['slug']}-{day.isoformat()}",
            description=problem["description"],
            constraints=problem.get("constraints", ""),
            difficulty=problem["difficulty"],
            release_date=day,
            function_name=problem["function_name"],
            params=problem["params"],
            reference_python=problem["reference_python"],
            reference_javascript=problem.get("reference_javascript", ""),
            examples=problem["examples"],
            hidden=problem["hidden"],
            performance=problem.get("performance", []),
            hints=problem.get("hints", []),
            explanation=problem.get("explanation", ""),
        )
    except IntegrityError:  # another request created it first
        return Challenge.objects.get(release_date=day, team__isnull=True)


def todays_challenge():
    return ensure_daily_challenge(utc_today())


def upcoming_days(count=3):
    today = utc_today()
    return [
        {"date": today + timedelta(days=i), "difficulty": problem_bank.problem_for_date(today + timedelta(days=i))["difficulty"]}
        for i in range(1, count + 1)
    ]


# ------------------------------------------------------------- participation

def find_participation(user, challenge):
    """The entry this user is currently playing for this challenge (team entry wins)."""
    team = user.profile.active_team
    if team:
        entry = Participation.objects.filter(challenge=challenge, team=team).first()
        if entry:
            return entry
    return Participation.objects.filter(challenge=challenge, user=user, team__isnull=True).first()


def start_participation(user, challenge, mode="solo"):
    existing = find_participation(user, challenge)
    if existing:
        return existing
    team = user.profile.active_team if mode == "team" else None
    if mode == "team" and not team:
        raise ChallengeError("Join a team first to play in team mode.")
    if challenge.team_id and team and team.pk != challenge.team_id:
        team = None
    try:
        with transaction.atomic():
            if team:
                entry, _ = Participation.objects.get_or_create(challenge=challenge, team=team)
            else:
                entry, _ = Participation.objects.get_or_create(challenge=challenge, user=user, team=None)
    except IntegrityError:
        entry = find_participation(user, challenge)
    if challenge.is_closed and not entry.solved:
        entry.is_practice = True
        entry.save(update_fields=["is_practice"])
    return entry


def _check_can_play(user, challenge):
    if not challenge.is_visible_to(user):
        raise ChallengeError("This challenge is not available.")


def _validate_language(language):
    if language not in runner.available_languages():
        raise ChallengeError(f"Language '{language}' is not supported on this server.")


def run_examples(user, challenge, code, language):
    """'Run' button: example tests only, never counts as an attempt."""
    _check_can_play(user, challenge)
    _validate_language(language)
    if error := anticheat.check_rate_limit(user, "run"):
        raise ChallengeError(error)
    tests = challenge.tests.filter(is_example=True)
    return runner.run_tests(language, code, challenge.function_for(language), tests)


def _reference_measurements(challenge, language, tests):
    code = challenge.reference_javascript if language == "javascript" and challenge.reference_javascript else challenge.reference_python
    lang = "javascript" if language == "javascript" and challenge.reference_javascript else "python"
    result = runner.run_tests(lang, code, challenge.function_for(lang), tests)
    return result.total_runtime_ms, result.memory_kb


def submit(user, challenge, code, language, *, via_api=False):
    """Full submission: every test. Returns (submission, run_result, participation)."""
    _check_can_play(user, challenge)
    _validate_language(language)
    if not code.strip():
        raise ChallengeError("Your solution is empty.")
    if len(code) > 50_000:
        raise ChallengeError("Solutions are limited to 50,000 characters.")
    if error := anticheat.check_rate_limit(user, "submit"):
        raise ChallengeError(error)

    entry = start_participation(user, challenge)
    if entry.solved:
        raise ChallengeError("Already solved! Your score is locked in — check the leaderboard.")

    tests = list(challenge.tests.all())
    result = runner.run_tests(language, code, challenge.function_for(language), tests)
    submission = Submission.objects.create(
        participation=entry, user=user, language=language, code=code, status=result.status,
        passed_count=result.passed_count, total_count=len(tests), via_api=via_api,
        runtime_ms=round(result.total_runtime_ms, 3) if result.cases else None,
        memory_kb=result.memory_kb or None,
    )

    if result.status != "accepted":
        Participation.objects.filter(pk=entry.pk).update(failed_attempts=entry.failed_attempts + 1)
        entry.refresh_from_db()
        return submission, result, entry

    perf_tests = [t for t in tests if t.is_performance] or tests
    user_perf_ms = sum(c.ms for t, c in zip(tests, result.cases) if t in perf_tests)
    ref_ms, ref_mem = _reference_measurements(challenge, language, perf_tests)

    now = timezone.now()
    late = now >= challenge.closes_at
    entry.solved_at = now
    entry.language = language
    entry.is_practice = entry.is_practice or late
    penalty = entry.hint_usages.aggregate(total=Sum("hint__cost"))["total"] or 0
    breakdown = scoring.score(
        solved=True, failed_attempts=entry.failed_attempts, solve_seconds=entry.solve_seconds,
        runtime_ms=user_perf_ms, reference_runtime_ms=ref_ms,
        memory_kb=result.memory_kb, reference_memory_kb=ref_mem, hint_penalty=penalty,
    )
    entry.correctness_points = breakdown.correctness
    entry.attempt_points = breakdown.attempts
    entry.speed_points = breakdown.speed
    entry.efficiency_points = breakdown.efficiency
    entry.hint_penalty = breakdown.hint_penalty
    entry.score = breakdown.total
    entry.save()

    anticheat.flag_if_similar(submission)
    _update_streaks(user, entry, challenge, late)
    fire_webhooks(entry, submission)
    return submission, result, entry


def _update_streaks(user, entry, challenge, late):
    if challenge.team_id:
        return  # private group challenges don't count toward daily streaks
    members = entry.team.active_members if entry.team_id else [user]
    today = utc_today()
    for member in members:
        if not late:
            streaks.record_day(member, challenge.release_date, StreakDay.SOLVED)
        elif challenge.release_date == today - timedelta(days=1):
            streaks.record_day(member, challenge.release_date, StreakDay.RECOVERED)


def reveal_hint(user, challenge):
    _check_can_play(user, challenge)
    entry = start_participation(user, challenge)
    used = set(entry.hint_usages.values_list("hint_id", flat=True))
    next_hint = challenge.hints.exclude(pk__in=used).first()
    if not next_hint:
        raise ChallengeError("No more hints for this challenge.")
    if entry.solved:
        raise ChallengeError("You already solved it — hints are free to read in the explanation once the challenge closes.")
    HintUsage.objects.get_or_create(participation=entry, hint=next_hint, defaults={"user": user})
    return next_hint


def revealed_hints(entry):
    if not entry:
        return []
    return [u.hint for u in entry.hint_usages.select_related("hint").order_by("hint__order")]


# ------------------------------------------------------------------ webhooks

def fire_webhooks(entry, submission):
    users = entry.team.active_members if entry.team_id else [entry.user]
    payload = {
        "event": "challenge.solved",
        "challenge": entry.challenge.slug,
        "title": entry.challenge.title,
        "solved_by": submission.user.username,
        "team": entry.team.name if entry.team_id else None,
        "score": entry.score,
        "language": entry.language,
        "solve_seconds": entry.solve_seconds,
    }
    for user in users:
        url = user.profile.webhook_url
        if url:
            threading.Thread(target=_post_json, args=(url, payload), daemon=True).start()


def _post_json(url, payload):
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "User-Agent": "ReCode-Webhook/1.0"}
        )
        urllib.request.urlopen(req, timeout=5).close()
    except Exception as exc:  # noqa: BLE001 - webhooks are best effort
        log.warning("Webhook to %s failed: %s", url, exc)


# -------------------------------------------------------------------- stats

def user_entries(user):
    """All participations that count for this user: solo ones plus team ones they contributed to."""
    return Participation.objects.filter(Q(submissions__user=user) | Q(user=user, team__isnull=True)).distinct()


def user_stats(user):
    entries = user_entries(user)
    solved = entries.filter(solved_at__isnull=False)
    ranked = solved.filter(is_practice=False)
    langs = (
        Submission.objects.filter(user=user, status="accepted").values("language").annotate(n=Count("id")).order_by("-n")
    )
    total_langs = sum(row["n"] for row in langs) or 1
    return {
        "solved": solved.count(),
        "attempted": entries.count(),
        "total_score": round(sum(e.score for e in ranked), 1),
        "avg_score": round(sum(e.score for e in ranked) / ranked.count(), 1) if ranked.exists() else 0,
        "perfect": ranked.filter(score__gte=99.5).count(),
        "submissions": Submission.objects.filter(user=user).count(),
        "languages": [{"language": row["language"], "count": row["n"], "pct": round(100 * row["n"] / total_langs)} for row in langs],
    }


BADGES = [
    ("first-blood", "First Solve", "Solved your first challenge", "🏁"),
    ("streak-7", "On Fire", "Reached a 7 day streak", "🔥"),
    ("streak-30", "Unstoppable", "Reached a 30 day streak", "☄️"),
    ("perfect", "Flawless", "Scored 100 on a challenge", "💯"),
    ("speedster", "Speedster", "Solved a challenge in under 5 minutes", "⚡"),
    ("clean", "Clean Sheet", "Solved 5 challenges with zero failed attempts", "🧼"),
    ("polyglot", "Polyglot", "Solved challenges in 2+ languages", "🌐"),
    ("team-player", "Team Player", "Solved a challenge with a team", "🤝"),
    ("no-hints", "Self-Made", "Solved 10 challenges without hints", "🧠"),
    ("social", "Contributor", "Posted 5 discussion comments", "💬"),
]


def badges_for(user):
    entries = user_entries(user).filter(solved_at__isnull=False)
    earned = set()
    if entries.exists():
        earned.add("first-blood")
    longest = user.profile.longest_streak
    if longest >= 7:
        earned.add("streak-7")
    if longest >= 30:
        earned.add("streak-30")
    if entries.filter(score__gte=99.5).exists():
        earned.add("perfect")
    if any((e.solve_seconds or 10**9) < 300 for e in entries):
        earned.add("speedster")
    if entries.filter(failed_attempts=0).count() >= 5:
        earned.add("clean")
    if Submission.objects.filter(user=user, status="accepted").values("language").distinct().count() >= 2:
        earned.add("polyglot")
    if entries.filter(team__isnull=False).exists():
        earned.add("team-player")
    if entries.filter(hint_usages__isnull=True).count() >= 10:
        earned.add("no-hints")
    if user.comments.count() >= 5:
        earned.add("social")
    return [
        {"key": key, "name": name, "description": desc, "icon": icon, "earned": key in earned}
        for key, name, desc, icon in BADGES
    ]
