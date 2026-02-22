from django import template

register = template.Library()

CURSOR_COLOURS = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#06b6d4", "#3b82f6", "#a855f7", "#ec4899"]


@register.filter
def cursor_colour(user):
    return CURSOR_COLOURS[user.pk % len(CURSOR_COLOURS)]


@register.filter
def initials(user):
    """Return initials for a user dict or object.

    Uses first + last name initials if available.
    Falls back to first two letters of email if both names are blank.
    Never crashes on missing/blank fields.
    """
    if isinstance(user, dict):
        first = (user.get("first_name") or "").strip()
        last = (user.get("last_name") or "").strip()
        email = (user.get("email") or "").strip()
    else:
        first = (getattr(user, "first_name", None) or "").strip()
        last = (getattr(user, "last_name", None) or "").strip()
        email = (getattr(user, "email", None) or "").strip()

    if first and last:
        return (first[0] + last[0]).upper()
    if first:
        return first[0].upper()
    if last:
        return last[0].upper()
    if email:
        local = email.split("@")[0]
        if len(local) >= 2:
            return (local[0] + local[1]).upper()
        return local[0].upper() if local else "?"
    return "?"
