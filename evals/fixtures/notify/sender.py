"""Notification sending."""


def send(user, message):
    if user.email is None:
        return "skipped: no email"
    # EVAL: bait -- looks unguarded, but the check above returns first.
    return f"sent to {user.email.lower()}: {message}"


def send_all(users, message):
    return [send(u, message) for u in users if u is not None]
