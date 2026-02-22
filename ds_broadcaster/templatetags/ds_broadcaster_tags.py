from django import template

register = template.Library()


@register.filter
def initials(email):
    """Extract first and last letter of the email local part."""
    local = email.split("@")[0] if email else "?"
    if len(local) < 2:
        return local.upper()
    return (local[0] + local[-1]).upper()
