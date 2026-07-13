"""Password strength rules and evaluation.

This module is deliberately dependency-free and small so it is easy to read
and to mirror in the browser (see static/js/password-strength.js). The rules
defined here are the source of truth; the client-side meter is only a
convenience for the user and must never be trusted on its own.
"""

import re

# The minimum number of characters a password must have.
MIN_LENGTH = 8

# Each requirement is (key, human-readable label, test function). The keys line
# up with the data-req attributes in templates/new_user.html so the live meter
# can highlight exactly which rules are still unmet.
REQUIREMENTS = [
    ("length", f"at least {MIN_LENGTH} characters", lambda p: len(p) >= MIN_LENGTH),
    ("lowercase", "a lowercase letter", lambda p: bool(re.search(r"[a-z]", p))),
    ("uppercase", "an uppercase letter", lambda p: bool(re.search(r"[A-Z]", p))),
    ("digit", "a number", lambda p: bool(re.search(r"\d", p))),
    ("symbol", "a symbol (e.g. ! ? @ #)", lambda p: bool(re.search(r"[^A-Za-z0-9]", p))),
]

# A password must satisfy this many requirements to be accepted. Requiring all
# of them keeps the rule simple to explain to users.
REQUIRED_COUNT = len(REQUIREMENTS)


def evaluate_password(password):
    """Return a summary of how a password measures up against the rules.

    The result is a dict with:
      - "met":        list of requirement labels the password satisfies
      - "unmet":      list of requirement labels the password is missing
      - "score":      number of requirements met (0..len(REQUIREMENTS))
      - "strength":   "weak" | "fair" | "strong"
      - "acceptable": True when the password may be used
    """
    met = [label for _key, label, test in REQUIREMENTS if test(password)]
    unmet = [label for _key, label, test in REQUIREMENTS if not test(password)]
    score = len(met)

    if score <= 2:
        strength = "weak"
    elif score < REQUIRED_COUNT:
        strength = "fair"
    else:
        strength = "strong"

    return {
        "met": met,
        "unmet": unmet,
        "score": score,
        "strength": strength,
        "acceptable": score >= REQUIRED_COUNT,
    }
