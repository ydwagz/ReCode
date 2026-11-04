from datetime import timedelta

from django.core.management.base import BaseCommand

from App import runner, services
from App.models import Challenge, utc_today


class Command(BaseCommand):
    help = "Schedule daily challenges from the problem bank (past and future days) and verify JS references."

    def add_arguments(self, parser):
        parser.add_argument("--past", type=int, default=14, help="Days before today to fill")
        parser.add_argument("--future", type=int, default=7, help="Days after today to fill")

    def handle(self, *args, past, future, **options):
        today = utc_today()
        created = 0
        for offset in range(-past, future + 1):
            day = today + timedelta(days=offset)
            existed = Challenge.objects.filter(release_date=day, team__isnull=True).exists()
            challenge = services.ensure_daily_challenge(day)
            created += not existed
            if not existed and challenge.reference_javascript and "javascript" in runner.available_languages():
                result = runner.run_tests("javascript", challenge.reference_javascript, challenge.js_function_name, challenge.tests.all())
                if result.status != "accepted":
                    self.stderr.write(self.style.WARNING(f"JS reference for {challenge.slug} failed: {result.status} {result.error}"))
        self.stdout.write(self.style.SUCCESS(f"{created} challenge(s) created; {past + future + 1} days covered."))
