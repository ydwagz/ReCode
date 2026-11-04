from django.contrib import admin

from .models import (
    Challenge,
    Comment,
    Hint,
    Participation,
    Profile,
    StreakDay,
    Submission,
    Team,
    TeamMembership,
    TeamMessage,
    TestCase,
)


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 0


class HintInline(admin.TabularInline):
    model = Hint
    extra = 0


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("title", "release_date", "difficulty", "team")
    list_filter = ("difficulty", "release_date")
    search_fields = ("title", "slug")
    inlines = [TestCaseInline, HintInline]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("user", "participation", "language", "status", "flagged", "similarity", "created_at")
    list_filter = ("status", "flagged", "language")
    search_fields = ("user__username",)
    raw_id_fields = ("participation", "similar_to")


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ("challenge", "user", "team", "score", "solved_at", "failed_attempts", "is_practice")
    list_filter = ("is_practice",)


class MembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    inlines = [MembershipInline]


admin.site.register(Profile)
admin.site.register(Comment)
admin.site.register(TeamMessage)
admin.site.register(StreakDay)
