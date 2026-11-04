import json
import logging
from functools import wraps

from django.http import JsonResponse

log = logging.getLogger("recode")


def json_errors(view):
    """Turn unexpected crashes in JSON endpoints into a readable error (the traceback goes to the server log)."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if exc.__class__.__name__ in ("Http404", "PermissionDenied"):
                raise
            log.exception("Unhandled error in %s", request.path)
            return JsonResponse({"ok": False, "error": f"The judge crashed: {type(exc).__name__}: {exc}. Check the server console."}, status=500)

    return wrapper


def json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def json_error(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def serialize_run(result, show_expected=True):
    return {
        "status": result.status,
        "error": result.error,
        "stdout": result.stdout,
        "passed": result.passed_count,
        "total": len(result.cases),
        "runtime_ms": round(result.total_runtime_ms, 2),
        "cases": [
            {
                "passed": c.passed,
                "error": c.error,
                "stdout": c.stdout,
                "ms": round(c.ms, 3),
                "got": c.value if show_expected else None,
                "expected": c.expected if show_expected else None,
            }
            for c in result.cases
        ],
    }


def serialize_entry(entry):
    return {
        "solved": entry.solved,
        "score": entry.score,
        "practice": entry.is_practice,
        "failed_attempts": entry.failed_attempts,
        "solve_seconds": entry.solve_seconds,
        "breakdown": {
            "correctness": entry.correctness_points,
            "attempts": entry.attempt_points,
            "speed": entry.speed_points,
            "efficiency": entry.efficiency_points,
            "hint_penalty": entry.hint_penalty,
        },
    }


def safe_next(request, fallback):
    """A POSTed ?next= target, only if it points back at this site."""
    from django.utils.http import url_has_allowed_host_and_scheme

    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return fallback
