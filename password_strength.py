"""Password strength rules and evaluation.

The rules here are the source of truth; the meter in
static/js/password-strength.js only mirrors them and is never trusted on its
own. Requirement keys match the data-req attributes in new_user.html.
"""

import re

MIN_LENGTH = 8

REQUIREMENTS = [
    ("length", f"at least {MIN_LENGTH} characters", lambda p: len(p) >= MIN_LENGTH),
    ("lowercase", "a lowercase letter", lambda p: bool(re.search(r"[a-z]", p))),
    ("uppercase", "an uppercase letter", lambda p: bool(re.search(r"[A-Z]", p))),
    ("digit", "a number", lambda p: bool(re.search(r"\d", p))),
    ("symbol", "a symbol (e.g. ! ? @ #)", lambda p: bool(re.search(r"[^A-Za-z0-9]", p))),
]

REQUIRED_COUNT = len(REQUIREMENTS)


def evaluate_password(password):
    """Summarise how a password measures up against REQUIREMENTS.

    Returns a dict with "met"/"unmet" requirement labels, "score",
    "strength" ("weak" | "fair" | "strong"), and "acceptable" (True only
    when every requirement is met).
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
