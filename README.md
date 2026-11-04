**ReCode: Code. Compete. Improve.**

ReCode is a daily competitive coding platform. Every day at 00:00 UTC a new problem drops. Solve it solo or with a team of up to 5, and climb the live leaderboards. You can code in the browser, or pull the problem and submit from your own editor with the ReCode plugin. Streaks keep you coming back, and you can recover them if you miss a day.

## Quick start

```bash
pip install -r requirements.txt
python manage.py migrate                # creates your local db.sqlite3 (not tracked by git)
python manage.py seed_challenges        # schedule challenges for the past 14 and next 7 days
python manage.py seed_demo              # optional: 20 demo players, 3 teams, results and comments
python manage.py createsuperuser        # optional: for /admin/
python manage.py runserver
```

Open http://127.0.0.1:8000. All demo users share the password `recode-demo-123` (e.g. `luca`, `nia`, `emma`).

You don't have to seed anything. When no challenge exists for a day, ReCode generates one from the built-in problem bank the first time someone visits.

JavaScript support needs `node` on the server's `PATH`. Without it, only Python is offered.

Run the tests with:

```bash
python manage.py test App
```

## Features

| Area | What's there |
|------|--------------|
| **Daily challenge** | A new problem every day, open from 00:00 to 24:00 UTC. Past challenges stay open for practice, which is not ranked. |
| **Editor** | CodeMirror editor with Python and JavaScript, saved per challenge in local storage. *Run* checks the examples for free; *Submit* runs every test, including hidden tests and a large performance input. Shortcuts: <kbd>Ctrl/⌘ + '</kbd> runs, <kbd>Ctrl/⌘ + Enter</kbd> submits. |
| **Scoring (max 100)** | Correctness 60 (all tests or nothing). Attempts 20 (`20 × 0.75^fails`). Speed 10 (full within 5 minutes of pressing start, sliding to 1 at 3 hours). Efficiency 10 (runtime and memory compared with the reference solution). Ties are broken by solve time. See `App/scoring.py`. |
| **Hints** | Progressive. The first hint is free and each later one costs 3 points. Full explanations, all hints and the reference solution unlock after the deadline. |
| **Teams** | Up to 5 members. Invite by username or by link/code. Team chat, team streak, a private member leaderboard, and **private group challenges** (write your own problem; expected outputs are computed from your reference solution). A team plays as one shared entry: any member can submit. |
| **Leaderboards** | Daily (refreshes live every 10s), weekly and all-time. Filter by players or teams and by language, and search by name. |
| **Streaks** | Solving before the deadline keeps your streak. If you miss a day, solving *yesterday's* challenge today recovers it. Streak freezes (you start with 1, earn 1 per 7-day streak, max 2) cover gaps automatically. |
| **Community** | Discussion thread per challenge with replies and up/down votes, an activity feed, and solution galleries with likes that unlock when a challenge closes. |
| **Profile** | Stats, streak heatmap, language breakdown, 10 badges, past solutions and team history. Public profiles are at `/u/<username>/` and can be made private. |
| **Settings** | Account, default language, notification and privacy toggles, password, plugin token and webhooks. |
| **Anti-cheat** | Rate limiting (3s between runs, 40 submissions/hour). Copy detection compares token streams, so renaming variables doesn't hide a copy, and flags suspects in the admin. Hidden test inputs and outputs are never sent to the browser, and solutions stay private until the deadline. |

## Email verification

New accounts confirm their email with a 6-digit code before they can play. In development the email is printed in the `runserver` console, so look there for the code. To send real email, set these environment variables:

```bash
RECODE_EMAIL_HOST=smtp.example.com RECODE_EMAIL_PORT=587 RECODE_EMAIL_USER=... RECODE_EMAIL_PASSWORD=... RECODE_EMAIL_FROM="ReCode <no-reply@example.com>"
```

Accounts that existed before verification was added are marked as verified automatically.

## IDE plugin and API

Get your token from **Settings → Integrations**.

* **Any editor:** `plugins/recode_cli.py` uses only the standard library. Commands are `pull`, `test` (local), `run`, `submit [--team]` and `me`.
* **VS Code:** `plugins/vscode/`. Its commands are *Pull Today's Challenge*, *Run Examples* and *Submit Current File*, and your streak shows in the status bar. See its README.
* **REST:** send `Authorization: Token <token>`. Endpoints are `GET /api/v1/me/`, `GET /api/v1/today/`, `GET /api/v1/challenges/<slug>/`, `POST /api/v1/run/` and `POST /api/v1/submit/`.
* **Webhooks:** ReCode POSTs a `challenge.solved` JSON event to your URL whenever you or your team solve a challenge.

## Project layout

```
App/
  models.py          Challenge, TestCase, Hint, Participation, Submission, Team, StreakDay, Comment, …
  runner.py          runs player code in a separate process with CPU/memory/time limits
  scoring.py         the 100-point formula
  streaks.py         streaks, recovery and freezes
  leaderboards.py    ranking queries
  anticheat.py       rate limits and similarity detection
  services.py        submit / hints / participation logic shared by the web views and the API
  problem_bank.py    14 built-in problems with Python and JS reference solutions
  views/             pages, challenges, teams, community, api
  management/commands/seed_challenges.py, seed_demo.py
plugins/
  recode_cli.py      CLI plugin
  vscode/            VS Code extension
```

## Production notes

* Set `RECODE_SECRET_KEY`, `RECODE_DEBUG=0` and `RECODE_ALLOWED_HOSTS`.
* `runner.py` isolates code with a separate process, rlimits, a timeout and an empty environment. That is fine for friends and classrooms. A public deployment should also run the code inside a container or nsjail.
* Live features use short polling, so no extra services are needed. For many concurrent users, swap the locmem cache for Redis.
