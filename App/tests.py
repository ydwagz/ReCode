import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from . import anticheat, leaderboards, runner, scoring, services, streaks
from .models import Participation, StreakDay, Submission, Team, TeamMembership, utc_today

GOOD_TWO_SUM = """
def two_sum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        if target - n in seen:
            return [seen[target - n], i]
        seen[n] = i
"""
BAD_TWO_SUM = "def two_sum(nums, target):\n    return [0, 1]\n"


def make_user(*args, **kwargs):
    return User.objects.create_user(*args, **kwargs)


def make_two_sum(day=None, **extra):
    from .problem_bank import PROBLEMS

    problem = next(p for p in PROBLEMS if p["slug"] == "two-sum")
    day = day or utc_today()
    return services.create_challenge(
        title="Two Sum", slug=f"two-sum-{day}-{extra.get('team').slug if extra.get('team') else 'public'}",
        description=problem["description"], release_date=day, function_name="two_sum", params="nums, target",
        reference_python=problem["reference_python"], reference_javascript=problem["reference_javascript"],
        examples=problem["examples"], hidden=problem["hidden"], hints=["free hint", "paid hint"], **extra,
    )


class ScoringTests(TestCase):
    def test_unsolved_scores_zero(self):
        self.assertEqual(scoring.score(solved=False, failed_attempts=0, solve_seconds=1, runtime_ms=1, reference_runtime_ms=1).total, 0)

    def test_perfect_score_is_100(self):
        s = scoring.score(solved=True, failed_attempts=0, solve_seconds=60, runtime_ms=1, reference_runtime_ms=1, memory_kb=100, reference_memory_kb=100)
        self.assertEqual(s.total, 100)

    def test_attempts_have_diminishing_returns(self):
        points = [scoring.attempt_points(n) for n in range(6)]
        self.assertEqual(points[0], 20)
        drops = [a - b for a, b in zip(points, points[1:])]
        self.assertTrue(all(d1 > d2 for d1, d2 in zip(drops, drops[1:])))

    def test_speed_is_bounded(self):
        self.assertEqual(scoring.speed_points(10), 10)
        self.assertEqual(scoring.speed_points(10**6), scoring.SPEED_FLOOR_POINTS)
        self.assertTrue(1 < scoring.speed_points(3600) < 10)

    def test_slow_code_loses_efficiency(self):
        self.assertEqual(scoring.efficiency_points(1.0, 1.0), 10)
        self.assertLess(scoring.efficiency_points(100.0, 1.0), 4)

    def test_hint_penalty_never_goes_negative(self):
        s = scoring.score(solved=True, failed_attempts=50, solve_seconds=10**6, runtime_ms=1e6, reference_runtime_ms=1,
                          memory_kb=10**6, reference_memory_kb=1, hint_penalty=500)
        self.assertEqual(s.total, 0)


class RunnerTests(TestCase):
    def test_python_and_output_capture(self):
        raw = runner.execute("python", "def f(a, b):\n    print('dbg')\n    return a + b\n", "f", [{"args": [1, 2]}])
        self.assertEqual(raw["results"][0]["value"], 3)
        self.assertIn("dbg", raw["results"][0]["stdout"])

    def test_infinite_loop_times_out(self):
        with mock.patch.object(runner, "CPU_LIMIT_SECONDS", 1):
            self.assertTrue(runner.execute("python", "def f():\n    while True: pass\n", "f", [{"args": []}]).get("timeout"))

    def test_spoofed_output_is_ignored(self):
        code = "print('@@RECODE-fake@@{\"results\": []}')\ndef f():\n    return 1\n"
        raw = runner.execute("python", code, "f", [{"args": []}])
        self.assertEqual(raw["results"][0]["value"], 1)

    def test_missing_function(self):
        self.assertIn("not defined", runner.execute("python", "x = 1", "f", [])["compile_error"])

    def test_values_equal(self):
        self.assertTrue(runner.values_equal(0.1 + 0.2, 0.3))
        self.assertFalse(runner.values_equal(True, 1))
        self.assertTrue(runner.values_equal([[1, 2]], [[1, 2]]))

    def test_works_where_preexec_fn_is_unsupported(self):
        """Windows: subprocess raises ValueError for preexec_fn — this used to cause HTTP 500 on submit."""
        real_run = runner.subprocess.run

        def windows_run(*args, **kwargs):
            if kwargs.get("preexec_fn"):
                raise ValueError("preexec_fn is not supported on Windows platforms")
            return real_run(*args, **kwargs)

        with mock.patch.object(runner, "IS_POSIX", False), mock.patch.object(runner.subprocess, "run", windows_run):
            raw = runner.execute("python", "def f():\n    return 7\n", "f", [{"args": []}])
        self.assertEqual(raw["results"][0]["value"], 7)

    def test_works_when_a_resource_limit_is_rejected(self):
        """macOS rejects RLIMIT_AS — this used to cause HTTP 500 on submit."""
        import resource

        real_set = resource.setrlimit

        def mac_setrlimit(which, limits):
            if which == resource.RLIMIT_AS:
                raise ValueError("current limit exceeds maximum limit")
            return real_set(which, limits)

        with mock.patch("resource.setrlimit", mac_setrlimit):
            raw = runner.execute("python", "def f():\n    return 7\n", "f", [{"args": []}])
        self.assertEqual(raw["results"][0]["value"], 7)

    def test_harness_runs_without_resource_module(self):
        """Windows has no `resource` module; the harness must still report results."""
        code = "import sys\nsys.modules['resource'] = None\ndef f():\n    return 7\n"
        raw = runner.execute("python", code, "f", [{"args": []}])
        self.assertEqual(raw["results"][0]["value"], 7)

    def test_javascript(self):
        if "javascript" not in runner.available_languages():
            self.skipTest("node not installed")
        raw = runner.execute("javascript", "function twoX(n) { return n * 2 }", "twoX", [{"args": [21]}])
        self.assertEqual(raw["results"][0]["value"], 42)


class StreakTests(TestCase):
    def setUp(self):
        self.user = make_user("streaker", password="pw-123456!")
        self.today = utc_today()

    def day(self, n):
        return self.today - timedelta(days=n)

    def test_consecutive_days(self):
        for n in (2, 1, 0):
            streaks.record_day(self.user, self.day(n))
        status = streaks.streak_status(self.user)
        self.assertEqual((status["current"], status["state"]), (3, "active"))

    def test_freeze_covers_gap(self):
        streaks.record_day(self.user, self.day(2))
        streaks.record_day(self.user, self.day(0))  # missed day 1; the starter freeze covers it
        self.user.profile.refresh_from_db()
        self.assertEqual(streaks.streak_status(self.user)["current"], 3)
        self.assertEqual(self.user.profile.streak_freezes, 0)
        self.assertTrue(StreakDay.objects.filter(user=self.user, date=self.day(1), kind=StreakDay.FROZEN).exists())

    def test_big_gap_breaks(self):
        streaks.record_day(self.user, self.day(10))
        self.assertEqual(streaks.streak_status(self.user)["state"], "broken")

    def test_recoverable_after_one_missed_day(self):
        self.user.profile.streak_freezes = 0
        self.user.profile.save()
        streaks.record_day(self.user, self.day(2))
        self.assertEqual(streaks.streak_status(self.user)["state"], "recoverable")
        streaks.record_day(self.user, self.day(1), StreakDay.RECOVERED)
        self.assertEqual(streaks.streak_status(self.user)["current"], 2)

    def test_earn_freeze_every_week(self):
        self.user.profile.streak_freezes = 0
        self.user.profile.save()
        for n in range(6, -1, -1):
            streaks.record_day(self.user, self.day(n))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.streak_freezes, 1)
        self.assertEqual(self.user.profile.longest_streak, 7)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class SubmissionFlowTests(TestCase):
    def setUp(self):
        self.user = make_user("alice", password="pw-123456!")
        self.challenge = make_two_sum()

    def test_expected_outputs_come_from_reference(self):
        first = self.challenge.tests.first()
        self.assertEqual(first.expected, [0, 1])

    def test_wrong_then_right(self):
        sub, result, entry = services.submit(self.user, self.challenge, BAD_TWO_SUM, "python")
        self.assertEqual(result.status, "wrong")
        self.assertEqual(entry.failed_attempts, 1)
        sub, result, entry = services.submit(self.user, self.challenge, GOOD_TWO_SUM, "python")
        self.assertEqual(result.status, "accepted")
        self.assertTrue(entry.solved)
        self.assertEqual(entry.attempt_points, 15)
        self.assertGreater(entry.score, 80)
        self.assertEqual(streaks.streak_status(self.user)["state"], "active")
        with self.assertRaises(services.ChallengeError):
            services.submit(self.user, self.challenge, GOOD_TWO_SUM, "python")

    def test_hints_cost_points(self):
        services.reveal_hint(self.user, self.challenge)  # free
        services.reveal_hint(self.user, self.challenge)  # costs 3
        _, _, entry = services.submit(self.user, self.challenge, GOOD_TWO_SUM, "python")
        self.assertEqual(entry.hint_penalty, 3)

    def test_late_solve_is_practice(self):
        old = make_two_sum(day=utc_today() - timedelta(days=5))
        _, _, entry = services.submit(self.user, old, GOOD_TWO_SUM, "python")
        self.assertTrue(entry.is_practice)
        self.assertEqual(leaderboards.ranked_entries("alltime"), [])

    def test_yesterday_late_solve_recovers_streak(self):
        yesterday = make_two_sum(day=utc_today() - timedelta(days=1))
        services.submit(self.user, yesterday, GOOD_TWO_SUM, "python")
        self.assertEqual(StreakDay.objects.get(user=self.user).kind, StreakDay.RECOVERED)

    def test_future_challenge_hidden(self):
        future = make_two_sum(day=utc_today() + timedelta(days=2))
        with self.assertRaises(services.ChallengeError):
            services.submit(self.user, future, GOOD_TWO_SUM, "python")

    def test_unexpected_judge_crash_returns_json_not_html_500(self):
        self.client.login(username="alice", password="pw-123456!")
        url = self.challenge.get_absolute_url() + "submit/"
        with mock.patch.object(services.runner, "run_tests", side_effect=RuntimeError("boom")), self.assertLogs("recode", "ERROR"):
            response = self.client.post(url, json.dumps({"code": GOOD_TWO_SUM, "language": "python"}), content_type="application/json")
        self.assertEqual(response.status_code, 500)
        self.assertIn("boom", response.json()["error"])

    def test_web_endpoints(self):
        self.client.login(username="alice", password="pw-123456!")
        url = self.challenge.get_absolute_url()
        self.assertContains(self.client.get(url), "Your clock starts now.")
        self.client.post(url + "start/", {"mode": "solo"})
        run = self.client.post(url + "run/", json.dumps({"code": GOOD_TWO_SUM, "language": "python"}), content_type="application/json").json()
        self.assertEqual(run["result"]["status"], "accepted")
        bad = self.client.post(url + "submit/", json.dumps({"code": BAD_TWO_SUM, "language": "python"}), content_type="application/json").json()
        hidden = [c for c in bad["result"]["cases"] if c["expected"] is None]
        self.assertTrue(hidden, "hidden test data must not be returned")
        ok = self.client.post(url + "submit/", json.dumps({"code": GOOD_TWO_SUM, "language": "python"}), content_type="application/json").json()
        self.assertTrue(ok["entry"]["solved"])
        row = leaderboards.ranked_entries("daily")[0]
        self.assertEqual(row["key"], "alice")


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class TeamTests(TestCase):
    def setUp(self):
        self.users = [make_user(f"u{i}", password="pw-123456!") for i in range(6)]
        self.team = Team.objects.create(name="Null Pointers", owner=self.users[0])
        TeamMembership.objects.create(team=self.team, user=self.users[0])

    def join(self, user):
        self.client.force_login(user)
        return self.client.post(f"/teams/join/{self.team.invite_code}/", follow=True)

    def test_max_five_members(self):
        for user in self.users[1:5]:
            self.join(user)
        self.assertEqual(self.team.member_count, 5)
        response = self.join(self.users[5])
        self.assertContains(response, "is full")
        self.assertEqual(self.team.member_count, 5)

    def test_team_entry_is_shared(self):
        self.join(self.users[1])
        challenge = make_two_sum()
        services.start_participation(self.users[0], challenge, "team")
        services.submit(self.users[1], challenge, BAD_TWO_SUM, "python")
        _, _, entry = services.submit(self.users[0], challenge, GOOD_TWO_SUM, "python")
        self.assertEqual(entry.team, self.team)
        self.assertEqual(entry.failed_attempts, 1)
        self.assertEqual(Participation.objects.count(), 1)
        self.assertEqual(streaks.streak_status(self.users[1])["state"], "active")
        rows = leaderboards.ranked_entries("daily", scope="teams")
        self.assertEqual(rows[0]["name"], "Null Pointers")

    def test_private_challenge_visibility(self):
        challenge = make_two_sum(team=self.team)
        self.assertTrue(challenge.is_visible_to(self.users[0]))
        self.assertFalse(challenge.is_visible_to(self.users[3]))
        self.client.force_login(self.users[3])
        self.assertEqual(self.client.get(challenge.get_absolute_url()).status_code, 404)

    def test_chat(self):
        self.client.force_login(self.users[0])
        url = f"/teams/{self.team.slug}/chat/"
        data = self.client.post(url, json.dumps({"body": "hello"}), content_type="application/json").json()
        self.assertEqual(data["messages"][-1]["body"], "hello")
        self.client.force_login(self.users[4])
        self.assertEqual(self.client.get(url).status_code, 404)


class AntiCheatTests(TestCase):
    def test_renamed_copy_is_similar(self):
        renamed = GOOD_TWO_SUM.replace("seen", "lookup").replace("nums", "values").replace("n ", "x ").replace("n]", "x]")
        self.assertGreater(anticheat.similarity(GOOD_TWO_SUM, renamed, "python"), 0.9)

    def test_different_solution_is_not_similar(self):
        brute = """
def two_sum(nums, target):
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target:
                return [i, j]
    return []
"""
        self.assertLess(anticheat.similarity(GOOD_TWO_SUM, brute, "python"), 0.9)

    def test_rate_limit(self):
        self.assertIsNotNone(anticheat.rate_limit_error(timezone.now(), 0))
        self.assertIsNotNone(anticheat.rate_limit_error(None, anticheat.MAX_SUBMISSIONS_PER_HOUR))
        self.assertIsNone(anticheat.rate_limit_error(None, 0))

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
    def test_copied_submission_is_flagged(self):
        a = make_user("a", password="x")
        b = make_user("b", password="x")
        challenge = make_two_sum()
        services.submit(a, challenge, GOOD_TWO_SUM, "python")
        sub, _, _ = services.submit(b, challenge, GOOD_TWO_SUM.replace("seen", "memo"), "python")
        sub.refresh_from_db()
        self.assertTrue(sub.flagged)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class ApiTests(TestCase):
    def setUp(self):
        self.user = make_user("bob", password="pw-123456!")
        self.challenge = make_two_sum()
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.user.profile.api_token}"}

    def test_requires_token(self):
        self.assertEqual(self.client.get("/api/v1/today/").status_code, 401)

    def test_pull_and_submit(self):
        data = self.client.get("/api/v1/today/", **self.auth).json()
        self.assertEqual(data["challenge"]["slug"], self.challenge.slug)
        self.assertIn("def two_sum", data["challenge"]["starter_code"]["python"])
        res = self.client.post("/api/v1/submit/", json.dumps({"code": GOOD_TWO_SUM, "language": "python"}),
                               content_type="application/json", **self.auth).json()
        self.assertTrue(res["entry"]["solved"])
        self.assertTrue(Submission.objects.get().via_api)


class PageTests(TestCase):
    def test_public_pages_render(self):
        for url in ["/", "/challenges/", "/leaderboard/", "/community/", "/teams/", "/login/", "/register/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_register_creates_profile_and_logs_in(self):
        response = self.client.post("/register/", {"username": "newbie", "email": "new@example.com", "password1": "a-Strong-pass-42", "password2": "a-Strong-pass-42"})
        self.assertRedirects(response, "/dashboard/")
        self.assertTrue(User.objects.get(username="newbie").profile.api_token)

    def test_private_profile_hidden(self):
        user = make_user("shy", password="x")
        user.profile.public_profile = False
        user.profile.save()
        self.assertEqual(self.client.get("/u/shy/").status_code, 404)

    def setUp(self):
        cache.clear()



class RegistrationIsAtomicTests(TestCase):
    """A crash part-way through sign-up must not leave a half-made account behind."""

    data = {"username": "giorgi", "email": "g@example.com", "password1": "a-Strong-pass-42", "password2": "a-Strong-pass-42"}

    def test_failed_signup_leaves_no_account(self):
        from django.db import OperationalError

        self.client.raise_request_exception = False
        with mock.patch("App.signals.Profile.objects.get_or_create", side_effect=OperationalError("no such column")):
            self.client.post("/register/", self.data)
        self.assertFalse(User.objects.filter(username="giorgi").exists())
        response = self.client.post("/register/", self.data)
        self.assertRedirects(response, "/dashboard/")

    def test_cleanup_removes_only_broken_signups(self):
        from App.signups import remove_broken_signups

        good = make_user("good", password="x")
        broken = User.objects.create(username="broken", email="b@example.com")
        broken.profile.delete()
        self.assertEqual(remove_broken_signups(User), 1)
        self.assertTrue(User.objects.filter(pk=good.pk).exists())
        self.assertFalse(User.objects.filter(pk=broken.pk).exists())


class MissingMigrationMessageTests(TestCase):
    @override_settings(DEBUG=True)
    def test_explains_how_to_fix(self):
        from django.db import OperationalError

        self.client.raise_request_exception = False
        with mock.patch("App.views.accounts.RegisterForm.is_valid", side_effect=OperationalError("no such column: x")):
            response = self.client.post("/register/", {"username": "a"})
        self.assertContains(response, "python manage.py migrate", status_code=500)


class ProfileSettingsTests(TestCase):
    def setUp(self):
        self.user = make_user("olduser", password="x")  # created before email was required: email == ""
        self.client.force_login(self.user)

    def test_bio_saves_even_without_an_email(self):
        response = self.client.post("/settings/", {"section": "profile", "profile-display_name": "Old User", "profile-bio": "I like graphs"})
        self.assertRedirects(response, "/settings/#profile", fetch_redirect_response=False)
        self.user.profile.refresh_from_db()
        self.assertEqual((self.user.profile.display_name, self.user.profile.bio), ("Old User", "I like graphs"))

    def test_bio_shows_on_profile(self):
        self.client.post("/settings/", {"section": "profile", "profile-display_name": "", "profile-bio": "Hello there"})
        self.assertContains(self.client.get("/profile/"), "Hello there")

    def test_email_saves_without_any_code(self):
        response = self.client.post("/settings/", {"section": "email", "email-email": "old@example.com"})
        self.assertRedirects(response, "/settings/#email", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old@example.com")




class DotenvTests(TestCase):
    def test_reads_values_without_overriding_real_environment(self):
        import os
        import tempfile
        from pathlib import Path

        from Project.settings import _load_dotenv

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text('# comment\nRECODE_T_A=one\nRECODE_T_B="two words"\nRECODE_T_C=from-file\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {"RECODE_T_C": "from-env"}):
                _load_dotenv(path)
                self.assertEqual(os.environ["RECODE_T_A"], "one")
                self.assertEqual(os.environ["RECODE_T_B"], "two words")
                self.assertEqual(os.environ["RECODE_T_C"], "from-env")
            for key in ("RECODE_T_A", "RECODE_T_B"):
                os.environ.pop(key, None)



class NoEmailVerificationTests(TestCase):
    def test_sign_up_without_email_goes_straight_to_dashboard(self):
        data = {"username": "noemail", "email": "", "password1": "a-Strong-pass-42", "password2": "a-Strong-pass-42"}
        self.assertRedirects(self.client.post("/register/", data), "/dashboard/")
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)

    def test_sign_in_is_password_only(self):
        from django.core import mail

        make_user("plain", password="pw-123456!")
        response = self.client.post("/login/", {"username": "plain", "password": "pw-123456!"})
        self.assertRedirects(response, "/dashboard/")
        self.assertEqual(len(mail.outbox), 0)

    def test_verify_pages_are_gone(self):
        for url in ("/verify/", "/login/verify/"):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_duplicate_email_still_rejected(self):
        make_user("first", email="same@example.com", password="x")
        data = {"username": "second", "email": "SAME@example.com", "password1": "a-Strong-pass-42", "password2": "a-Strong-pass-42"}
        self.assertContains(self.client.post("/register/", data), "already in use")
