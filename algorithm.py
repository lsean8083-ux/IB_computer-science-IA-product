"""Pure, testable spaced-repetition calculations used by Trial_3."""
from datetime import datetime, timedelta

CORRECT_INTERVAL_MULTIPLIER = 3  # New interval is 300% of the old interval.
INCORRECT_INTERVAL_DAYS = 1
HIGH_PRIORITY_THRESHOLD = 10
HIGH_PRIORITY_WEIGHT = 5


def calculate_update(record, answer, current_time=None):
    """Return a new scheduling state without changing the database.

    ``y`` means "Yes, I know" and ``n`` means "No, I don't know".
    """
    answer = answer.strip().lower()
    if answer not in {"y", "yes", "n", "no"}:
        raise ValueError("Answer must be Y (Yes, I know) or N (No, I don't know).")
    now = current_time or datetime.now()
    known = answer in {"y", "yes"}
    if known:
        interval = max(1, float(record["interval_days"])) * CORRECT_INTERVAL_MULTIPLIER
        priority = max(0, int(record["priority"]) - 1)
        streak, correct = int(record["correct_streak"]) + 1, int(record["correct_count"]) + 1
    else:
        interval, priority = INCORRECT_INTERVAL_DAYS, int(record["priority"]) + 1
        streak, correct = 0, int(record["correct_count"])
    return {"priority": priority, "interval_days": interval,
            "next_review": (now + timedelta(days=interval)).isoformat(timespec="seconds"),
            "correct_streak": streak, "attempts": int(record["attempts"]) + 1,
            "correct_count": correct}


def selection_weight(record):
    """A priority above 10 receives explicit five-times selection weighting."""
    return HIGH_PRIORITY_WEIGHT if int(record["priority"]) > HIGH_PRIORITY_THRESHOLD else 1
