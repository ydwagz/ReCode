class MissingMigrationMiddleware:
    """In development, turn 'no such table/column' errors into a clear instruction."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from django.conf import settings
        from django.db import OperationalError, ProgrammingError
        from django.http import HttpResponse

        message = str(exception).lower()
        if settings.DEBUG and isinstance(exception, (OperationalError, ProgrammingError)) and (
            "no such table" in message or "no such column" in message
        ):
            return HttpResponse(
                "<h1>Database needs updating</h1><p>Stop the server and run:</p>"
                "<pre>python manage.py migrate</pre><p>Then start it again.</p>",
                status=500,
            )
        return None
