from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("settings/", views.settings_view, name="settings"),
    path("profile/", views.profile, name="profile"),
    path("u/<str:username>/", views.public_profile, name="public_profile"),

    # Challenges
    path("recode/", views.today_redirect, name="today"),
    path("challenges/", views.challenge_list, name="challenge_list"),
    path("challenges/<slug:slug>/", views.challenge_detail, name="challenge_detail"),
    path("challenges/<slug:slug>/start/", views.challenge_start, name="challenge_start"),
    path("challenges/<slug:slug>/run/", views.challenge_run, name="challenge_run"),
    path("challenges/<slug:slug>/submit/", views.challenge_submit, name="challenge_submit"),
    path("challenges/<slug:slug>/hint/", views.challenge_hint, name="challenge_hint"),
    path("challenges/<slug:slug>/progress/", views.challenge_progress, name="challenge_progress"),
    path("challenges/<slug:slug>/discussion/", views.challenge_discussion, name="challenge_discussion"),
    path("challenges/<slug:slug>/solutions/", views.solutions, name="solutions"),
    path("comments/<int:pk>/vote/", views.comment_vote, name="comment_vote"),
    path("submissions/<int:pk>/share/", views.submission_share, name="submission_share"),
    path("submissions/<int:pk>/like/", views.solution_like, name="solution_like"),

    # Leaderboards + community
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("leaderboard/data/", views.leaderboard_data, name="leaderboard_data"),
    path("community/", views.community, name="community"),

    # Teams
    path("teams/", views.teams, name="teams"),
    path("teams/create/", views.team_create, name="team_create"),
    path("teams/join/", views.team_join, name="team_join"),
    path("teams/join/<str:code>/", views.team_join_link, name="team_join_link"),
    path("teams/invites/<int:pk>/<str:action>/", views.invite_respond, name="invite_respond"),
    path("teams/<slug:slug>/", views.team_detail, name="team_detail"),
    path("teams/<slug:slug>/chat/", views.team_chat, name="team_chat"),
    path("teams/<slug:slug>/invite/", views.team_invite, name="team_invite"),
    path("teams/<slug:slug>/leave/", views.team_leave, name="team_leave"),
    path("teams/<slug:slug>/kick/<str:username>/", views.team_kick, name="team_kick"),
    path("teams/<slug:slug>/regenerate-code/", views.team_regenerate_code, name="team_regenerate_code"),
    path("teams/<slug:slug>/challenges/new/", views.team_private_challenge, name="team_private_challenge"),

    # Plugin / IDE API
    path("api/v1/me/", views.api_me, name="api_me"),
    path("api/v1/today/", views.api_today, name="api_today"),
    path("api/v1/challenges/<slug:slug>/", views.api_challenge, name="api_challenge"),
    path("api/v1/run/", views.api_run, name="api_run"),
    path("api/v1/submit/", views.api_submit, name="api_submit"),
]
