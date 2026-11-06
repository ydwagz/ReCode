import json
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_CODE_BLOCK = re.compile(r"```(?:\w+)?\n?(.*?)```", re.S)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")


@register.filter
def simple_md(text):
    """Tiny, safe markdown: ``` blocks, `inline`, **bold**, paragraphs. Everything is escaped first."""
    text = escape(text or "")
    blocks = []

    def stash(match):
        blocks.append(f"<pre class=\"md-pre\"><code>{match.group(1).strip()}</code></pre>")
        return f"\x00{len(blocks) - 1}\x00"

    text = _CODE_BLOCK.sub(stash, text)
    text = _INLINE_CODE.sub(r"<code>\1</code>", text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    paragraphs = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        if re.fullmatch(r"\x00\d+\x00", chunk.strip()):
            paragraphs.append(chunk.strip())
        else:
            paragraphs.append("<p>" + chunk.replace("\n", "<br>") + "</p>")
    html = "\n".join(paragraphs)
    html = re.sub(r"\x00(\d+)\x00", lambda m: blocks[int(m.group(1))], html)
    return mark_safe(html)


@register.filter
def duration(seconds):
    if seconds is None or seconds == "":
        return "—"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


@register.filter
def as_json(value):
    return json.dumps(value)


@register.filter
def initials(name):
    parts = str(name).split()
    return ("".join(p[0] for p in parts[:2]) or "?").upper()


@register.filter
def lang_label(code):
    return {"python": "Python", "javascript": "JavaScript"}.get(code, code or "—")


@register.filter
def field_input(bound_field):
    """Render a form field with the right Bootstrap class for its widget."""
    widget = bound_field.field.widget
    kind = getattr(widget, "input_type", "")
    if kind == "checkbox":
        css = "form-check-input"
    elif kind == "select" or widget.__class__.__name__ == "Select":
        css = "form-select"
    else:
        css = "form-control"
    existing = widget.attrs.get("class", "")
    if bound_field.errors:
        css += " is-invalid"
    return bound_field.as_widget(attrs={"class": f"{css} {existing}".strip()})


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.simple_tag
def format_args(args, params):
    """Render [[1, 2], 3] with params 'nums, target' as: nums = [1, 2], target = 3"""
    names = [p.strip() for p in params.split(",") if p.strip()]
    parts = []
    for i, value in enumerate(args):
        text = json.dumps(value)
        if len(text) > 300:
            text = text[:297] + "…"
        parts.append(f"{names[i]} = {text}" if i < len(names) else text)
    return ", ".join(parts)


@register.filter
def score_parts(entry):
    """The four scoring components as tiles: label, value, max, fill %, state."""
    parts = []
    for label, value, maximum in (
        ("Correct", entry.correctness_points, 60),
        ("Attempts", entry.attempt_points, 20),
        ("Speed", entry.speed_points, 10),
        ("Efficiency", entry.efficiency_points, 10),
    ):
        pct = round(100 * (value or 0) / maximum)
        parts.append({"label": label, "value": round(value or 0, 1), "max": maximum, "pct": pct,
                      "state": "full" if pct >= 99 else "partial" if pct > 0 else ""})
    return parts


@register.filter
def tone(name):
    """A stable colour slot (0-4) for a player or team name. Mirrors ReCode.tone() in recode.js."""
    return sum(ord(ch) for ch in str(name)) % 5
