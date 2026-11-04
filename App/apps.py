from django.apps import AppConfig


class RecodeConfig(AppConfig):
    name = "App"
    verbose_name = "ReCode"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa: F401
