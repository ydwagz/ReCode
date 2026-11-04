"""Anti-cheat helpers: submission rate limiting and code similarity detection."""

import difflib
import io
import re
import tokenize
from datetime import timedelta

from django.utils import timezone

MIN_SECONDS_BETWEEN_RUNS = 3
MAX_SUBMISSIONS_PER_HOUR = 40
SIMILARITY_THRESHOLD = 0.92
MIN_TOKENS_FOR_SIMILARITY = 25

_JS_TOKEN = re.compile(r"""[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|`(?:\\.|[^`])*`|\S""")
_JS_KEYWORDS = {
    "function", "return", "if", "else", "for", "while", "const", "let", "var", "of", "in", "new",
    "break", "continue", "true", "false", "null", "undefined", "Math", "length", "push", "pop",
}


def rate_limit_error(last_action_at, recent_count):
    if last_action_at and (timezone.now() - last_action_at).total_seconds() < MIN_SECONDS_BETWEEN_RUNS:
        return f"Slow down — wait {MIN_SECONDS_BETWEEN_RUNS} seconds between runs."
    if recent_count >= MAX_SUBMISSIONS_PER_HOUR:
        return "Submission limit reached for this hour. Take a breather and try again soon."
    return None


def check_rate_limit(user, cache_key_prefix="run"):
    """Returns an error string if the user is going too fast, else None. Uses submissions + cache."""
    from django.core.cache import cache

    from .models import Submission

    key = f"recode:{cache_key_prefix}:{user.pk}"
    last = cache.get(key)
    recent = Submission.objects.filter(user=user, created_at__gte=timezone.now() - timedelta(hours=1)).count()
    error = rate_limit_error(last, recent)
    if not error:
        cache.set(key, timezone.now(), timeout=60)
    return error


def normalize(code, language):
    """Token stream with identifiers/literals collapsed, so renaming variables doesn't hide copying."""
    tokens = []
    if language == "python":
        import keyword

        try:
            for tok in tokenize.generate_tokens(io.StringIO(code).readline):
                if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                                tokenize.DEDENT, tokenize.ENDMARKER):
                    continue
                if tok.type == tokenize.NAME:
                    tokens.append(tok.string if keyword.iskeyword(tok.string) else "ID")
                elif tok.type == tokenize.NUMBER:
                    tokens.append("NUM")
                elif tok.type == tokenize.STRING:
                    tokens.append("STR")
                else:
                    tokens.append(tok.string)
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return code.split()
    else:
        code = re.sub(r"//[^\n]*|/\*.*?\*/", "", code, flags=re.S)
        for tok in _JS_TOKEN.findall(code):
            if tok[0].isalpha() or tok[0] in "_$":
                tokens.append(tok if tok in _JS_KEYWORDS else "ID")
            elif tok[0].isdigit():
                tokens.append("NUM")
            elif tok[0] in "\"'`":
                tokens.append("STR")
            else:
                tokens.append(tok)
    return tokens


def similarity(code_a, code_b, language):
    a, b = normalize(code_a, language), normalize(code_b, language)
    if min(len(a), len(b)) < MIN_TOKENS_FOR_SIMILARITY:
        return 0.0  # tiny solutions legitimately look identical
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def flag_if_similar(submission):
    """Compare an accepted submission with other entrants' accepted code for the same challenge."""
    from .models import Submission

    participation = submission.participation
    others = (
        Submission.objects.filter(
            participation__challenge=participation.challenge, status="accepted", language=submission.language
        )
        .exclude(participation=participation)
        .exclude(created_at__gt=submission.created_at)
        .order_by("-created_at")[:200]
    )
    best, best_ratio = None, 0.0
    for other in others:
        ratio = similarity(submission.code, other.code, submission.language)
        if ratio > best_ratio:
            best, best_ratio = other, ratio
    if best and best_ratio >= SIMILARITY_THRESHOLD:
        submission.flagged = True
        submission.similar_to = best
        submission.similarity = round(best_ratio, 3)
        submission.save(update_fields=["flagged", "similar_to", "similarity"])
    return submission.flagged
