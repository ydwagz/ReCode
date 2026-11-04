import secrets
from datetime import datetime, time, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

LANGUAGE_CHOICES = [
    ("python", "Python"),
    ("javascript", "JavaScript"),
]

MAX_TEAM_SIZE = 5
MAX_STREAK_FREEZES = 2


def new_token():
    return secrets.token_hex(20)


def new_invite_code():
    return secrets.token_urlsafe(6)


def utc_today():
    return timezone.now().astimezone(dt_timezone.utc).date()


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=40, blank=True)
    bio = models.CharField(max_length=200, blank=True)
    default_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default="python")

    # Streaks
    streak_freezes = models.PositiveSmallIntegerField(default=1)
    longest_streak = models.PositiveIntegerField(default=0)

    # Notification + privacy preferences
    notify_daily = models.BooleanField(default=True, help_text="Remind me when a new challenge drops")
    notify_team = models.BooleanField(default=True, help_text="Notify me about team activity")
    notify_streak = models.BooleanField(default=True, help_text="Warn me when my streak is at risk")
    public_profile = models.BooleanField(default=True)
    show_on_leaderboard = models.BooleanField(default=True)

    # Email verification: unverified accounts can browse but not play.
    email_verified = models.BooleanField(default=False)

    # Integrations
    api_token = models.CharField(max_length=64, unique=True, default=new_token)
    webhook_url = models.URLField(blank=True)

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.display_name or self.user.username

    @property
    def active_team(self):
        membership = self.user.memberships.filter(active=True).select_related("team").first()
        return membership.team if membership else None


class Team(models.Model):
    name = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.CharField(max_length=200, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="owned_teams")
    invite_code = models.CharField(max_length=16, unique=True, default=new_invite_code)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "team"
            slug, n = base, 2
            while Team.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("team_detail", args=[self.slug])

    @property
    def active_members(self):
        return [m.user for m in self.memberships.filter(active=True).select_related("user__profile").order_by("joined_at")]

    @property
    def member_count(self):
        return self.memberships.filter(active=True).count()

    @property
    def is_full(self):
        return self.member_count >= MAX_TEAM_SIZE

    def has_member(self, user):
        return user.is_authenticated and self.memberships.filter(user=user, active=True).exists()


class TeamMembership(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-joined_at"]


class TeamInvite(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="invites")
    invited_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="team_invites")
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("team", "invited_user")]


class TeamMessage(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Challenge(models.Model):
    DIFFICULTIES = [("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")]

    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(help_text="Supports **bold**, `inline code` and ``` code blocks.")
    constraints = models.TextField(blank=True)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES, default="easy")
    release_date = models.DateField(db_index=True, help_text="Opens 00:00 UTC, closes 24h later.")
    function_name = models.CharField(max_length=60, help_text="Python name (snake_case). JS uses camelCase.")
    params = models.CharField(max_length=200, help_text="Comma separated parameter names")
    reference_python = models.TextField()
    reference_javascript = models.TextField(blank=True)
    explanation = models.TextField(blank=True, help_text="Shown after the challenge closes.")
    # Private group challenge: only visible to this team.
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.CASCADE, related_name="private_challenges")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-release_date"]

    def __str__(self):
        return f"{self.release_date} · {self.title}"

    def get_absolute_url(self):
        return reverse("challenge_detail", args=[self.slug])

    @property
    def opens_at(self):
        return datetime.combine(self.release_date, time.min, tzinfo=dt_timezone.utc)

    @property
    def closes_at(self):
        return self.opens_at + timedelta(days=1)

    @property
    def is_open(self):
        return self.opens_at <= timezone.now() < self.closes_at

    @property
    def is_closed(self):
        return timezone.now() >= self.closes_at

    @property
    def is_released(self):
        return timezone.now() >= self.opens_at

    @property
    def js_function_name(self):
        head, *rest = self.function_name.split("_")
        return head + "".join(part.capitalize() for part in rest)

    @property
    def param_list(self):
        return [p.strip() for p in self.params.split(",") if p.strip()]

    def starter_code(self, language):
        params = ", ".join(self.param_list)
        if language == "javascript":
            return f"function {self.js_function_name}({params}) {{\n  // your code here\n}}\n"
        return f"def {self.function_name}({params}):\n    # your code here\n    pass\n"

    def function_for(self, language):
        return self.js_function_name if language == "javascript" else self.function_name

    def is_visible_to(self, user):
        if user.is_authenticated and user.is_staff:
            return True
        if not self.is_released:
            return False
        if self.team_id:
            return self.team.has_member(user)
        return True


class TestCase(models.Model):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="tests")
    args = models.JSONField(help_text="List of positional arguments")
    expected = models.JSONField(null=True)
    is_example = models.BooleanField(default=False, help_text="Visible to players and used by Run")
    is_performance = models.BooleanField(default=False, help_text="Large input used for efficiency scoring")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class Hint(models.Model):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="hints")
    order = models.PositiveSmallIntegerField(default=1)
    text = models.TextField()
    cost = models.PositiveSmallIntegerField(default=3, help_text="Points deducted when revealed (0 = free)")

    class Meta:
        ordering = ["order"]


class Participation(models.Model):
    """One leaderboard entry: a solo player OR a team attempting one challenge."""

    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="participations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="participations")
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.CASCADE, related_name="participations")
    started_at = models.DateTimeField(default=timezone.now)
    solved_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, blank=True)
    is_practice = models.BooleanField(default=False, help_text="Solved after the deadline; not ranked")

    score = models.FloatField(default=0)
    correctness_points = models.FloatField(default=0)
    attempt_points = models.FloatField(default=0)
    speed_points = models.FloatField(default=0)
    efficiency_points = models.FloatField(default=0)
    hint_penalty = models.FloatField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["challenge", "user"], condition=models.Q(team__isnull=True), name="one_solo_entry"),
            models.UniqueConstraint(fields=["challenge", "team"], condition=models.Q(team__isnull=False), name="one_team_entry"),
            models.CheckConstraint(condition=models.Q(user__isnull=False) | models.Q(team__isnull=False), name="entry_has_owner"),
        ]

    @property
    def is_team(self):
        return self.team_id is not None

    @property
    def solved(self):
        return self.solved_at is not None

    @property
    def solve_seconds(self):
        if not self.solved_at:
            return None
        return max(0, int((self.solved_at - self.started_at).total_seconds()))

    @property
    def owner_name(self):
        return self.team.name if self.team_id else self.user.profile.name


class Submission(models.Model):
    STATUS = [("accepted", "Accepted"), ("wrong", "Wrong answer"), ("error", "Error"), ("timeout", "Time limit")]

    participation = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions")
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES)
    code = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS)
    passed_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    runtime_ms = models.FloatField(null=True, blank=True)
    memory_kb = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    via_api = models.BooleanField(default=False)
    shared = models.BooleanField(default=False, help_text="Show in the solution gallery once the challenge ends")
    flagged = models.BooleanField(default=False)
    similar_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    similarity = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class HintUsage(models.Model):
    participation = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name="hint_usages")
    hint = models.ForeignKey(Hint, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("participation", "hint")]


class StreakDay(models.Model):
    SOLVED, RECOVERED, FROZEN = "solved", "recovered", "frozen"
    KINDS = [(SOLVED, "Solved"), (RECOVERED, "Recovered"), (FROZEN, "Freeze used")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streak_days")
    date = models.DateField()
    kind = models.CharField(max_length=10, choices=KINDS)

    class Meta:
        unique_together = [("user", "date")]
        ordering = ["-date"]


class Comment(models.Model):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)
    score = models.IntegerField(default=0)

    class Meta:
        ordering = ["-score", "created_at"]


class CommentVote(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    value = models.SmallIntegerField(choices=[(1, "Up"), (-1, "Down")])

    class Meta:
        unique_together = [("comment", "user")]


class SolutionLike(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        unique_together = [("submission", "user")]


class EmailCode(models.Model):
    """A one-time 6-digit code e-mailed to confirm an address. Only a hash is stored."""

    TTL = timedelta(minutes=15)
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN = timedelta(seconds=60)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_codes")
    email = models.EmailField()
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    @property
    def expired(self):
        return timezone.now() >= self.created_at + self.TTL
