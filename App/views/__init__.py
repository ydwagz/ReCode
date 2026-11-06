from .accounts import login_view, logout_view, register
from .api import api_challenge, api_challenges, api_me, api_run, api_submit, api_today
from .challenges import (
    challenge_detail,
    challenge_discussion,
    challenge_hint,
    challenge_list,
    challenge_progress,
    challenge_run,
    challenge_start,
    challenge_submit,
    comment_vote,
    solution_like,
    solutions,
    submission_share,
    today_redirect,
)
from .community import community, leaderboard, leaderboard_data
from .pages import dashboard, home, profile, public_profile, settings_view
from .teams import (
    invite_respond,
    team_chat,
    team_create,
    team_detail,
    team_invite,
    team_join,
    team_join_link,
    team_kick,
    team_leave,
    team_private_challenge,
    team_regenerate_code,
    teams,
)
