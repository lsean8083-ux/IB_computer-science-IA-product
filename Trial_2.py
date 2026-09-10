"""Terminal vocabulary practice using an adaptive spaced-repetition algorithm."""

from datetime import datetime, timedelta
from pathlib import Path
import random
import sqlite3


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE_PATH = Path(__file__).with_name("Vocabulary_list_Trial_2.db")

CORRECT_INTERVAL_MULTIPLIER = 3
INCORRECT_INTERVAL_DAYS = 1

WEAK_WORD_THRESHOLD = 10
WEAK_WORD_WEIGHT = 5


# ============================================================
# VOCABULARY DATABASE CLASS
# ============================================================

class VocabularyDatabase:
    """
    Manages vocabulary data, the spaced-repetition algorithm,
    performance tracking, and vocabulary selection.
    """

    def __init__(self, database_path=DATABASE_PATH):

        self.database_path = str(database_path)

        self._create_schema()

    # --------------------------------------------------------
    # DATABASE CONNECTION
    # --------------------------------------------------------

    def _connect(self):
        """
        Creates a connection to the SQLite database.

        Returns:
            sqlite3.Connection
        """

        try:

            connection = sqlite3.connect(self.database_path)

            connection.row_factory = sqlite3.Row

            return connection

        except sqlite3.Error as error:

            raise RuntimeError(
                f"Could not connect to the vocabulary database: {error}"
            ) from error

    # --------------------------------------------------------
    # DATABASE SCHEMA
    # --------------------------------------------------------

    def _create_schema(self):
        """
        Creates the vocabulary table if it does not already exist.
        """

        with self._connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS words (

                    word TEXT PRIMARY KEY,

                    meaning TEXT NOT NULL,

                    priority INTEGER NOT NULL DEFAULT 0,

                    interval_days REAL NOT NULL DEFAULT 1,

                    next_review TEXT NOT NULL,

                    correct_streak INTEGER NOT NULL DEFAULT 0,

                    attempts INTEGER NOT NULL DEFAULT 0,

                    correct_count INTEGER NOT NULL DEFAULT 0

                )
                """
            )

    # --------------------------------------------------------
    # LOAD VOCABULARY
    # --------------------------------------------------------

    def load_vocabulary(self):
        """
        Retrieves all vocabulary records from the database.

        Returns:
            List of SQLite Row objects.
        """

        with self._connect() as connection:

            records = connection.execute(
                """
                SELECT
                    word,
                    meaning,
                    priority,
                    interval_days,
                    next_review,
                    correct_streak,
                    attempts,
                    correct_count
                FROM words
                ORDER BY word
                """
            ).fetchall()

        return records

    # --------------------------------------------------------
    # TIME FUNCTIONS
    # --------------------------------------------------------

    @staticmethod
    def _now():
        """
        Returns the current date and time.
        """

        return datetime.now()

    @staticmethod
    def _review_datetime(value):
        """
        Converts a stored ISO date string into a datetime object.

        Returns None if the stored value is invalid.
        """

        try:

            return datetime.fromisoformat(value)

        except (TypeError, ValueError):

            return None

    # --------------------------------------------------------
    # SPACED REPETITION ALGORITHM
    # --------------------------------------------------------

    def calculate_update(
        self,
        record,
        answer,
        current_time=None
    ):
        """
        Calculates how a vocabulary record changes after
        the user answers a question.

        Correct answer:
            interval × 3
            priority - 1
            correct streak + 1

        Incorrect answer:
            interval = 1 day
            priority + 1
            correct streak = 0

        The database is NOT changed by this method.
        """

        answer = answer.lower().strip()

        if answer not in {"y", "yes", "n", "no"}:

            raise ValueError(
                "Answer must be Y/yes or N/no."
            )

        now = current_time or self._now()

        is_correct = answer in {"y", "yes"}

        # ----------------------------------------------------
        # PERFORMANCE DATA
        # ----------------------------------------------------

        attempts = record["attempts"] + 1

        # ----------------------------------------------------
        # CORRECT ANSWER
        # ----------------------------------------------------

        if is_correct:

            correct_streak = (
                record["correct_streak"] + 1
            )

            correct_count = (
                record["correct_count"] + 1
            )

            # Increase review interval by ×3.
            interval_days = (
                max(1, record["interval_days"])
                * CORRECT_INTERVAL_MULTIPLIER
            )

            # Reduce priority, but never below zero.
            priority = max(
                0,
                record["priority"] - 1
            )

        # ----------------------------------------------------
        # INCORRECT ANSWER
        # ----------------------------------------------------

        else:

            # The user forgot the word.
            correct_streak = 0

            # Correct count does not increase.
            correct_count = record["correct_count"]

            # Review again in one day.
            interval_days = INCORRECT_INTERVAL_DAYS

            # Increase priority because the word is difficult.
            priority = record["priority"] + 1

        # ----------------------------------------------------
        # CALCULATE NEXT REVIEW DATE
        # ----------------------------------------------------

        next_review = (
            now + timedelta(days=interval_days)
        )

        # ----------------------------------------------------
        # RETURN NEW STATE
        # ----------------------------------------------------

        return {
            "priority": priority,
            "interval_days": interval_days,
            "next_review": next_review.isoformat(
                timespec="seconds"
            ),
            "correct_streak": correct_streak,
            "attempts": attempts,
            "correct_count": correct_count
        }

    # --------------------------------------------------------
    # SAVE ANSWER RESULT
    # --------------------------------------------------------

    def process_answer(self, record, answer):
        """
        Calculates the updated vocabulary state and saves
        only the vocabulary item that was just tested.
        """

        updates = self.calculate_update(
            record,
            answer
        )

        with self._connect() as connection:

            connection.execute(
                """
                UPDATE words

                SET
                    priority = ?,
                    interval_days = ?,
                    next_review = ?,
                    correct_streak = ?,
                    attempts = ?,
                    correct_count = ?

                WHERE word = ?
                """,

                (
                    updates["priority"],
                    updates["interval_days"],
                    updates["next_review"],
                    updates["correct_streak"],
                    updates["attempts"],
                    updates["correct_count"],
                    record["word"]
                )
            )

        return updates

    # --------------------------------------------------------
    # CHECK WHETHER WORD IS DUE
    # --------------------------------------------------------

    def is_due(self, record, current_time=None):
        """
        Determines whether a vocabulary item is ready
        for review.
        """

        now = current_time or self._now()

        review_time = self._review_datetime(
            record["next_review"]
        )

        # Invalid date = treat as immediately due.
        if review_time is None:

            return True

        return review_time <= now

    # --------------------------------------------------------
    # FIND DUE VOCABULARY
    # --------------------------------------------------------

    def get_due_vocabulary(self):
        """
        Returns vocabulary items whose review date has arrived.
        """

        records = self.load_vocabulary()

        return [
            record
            for record in records
            if self.is_due(record)
        ]

    # --------------------------------------------------------
    # CALCULATE SELECTION WEIGHT
    # --------------------------------------------------------

    @staticmethod
    def calculate_weight(record):
        """
        Determines the probability weight of a vocabulary item.

        Priority > 10:
            weight = 5

        Otherwise:
            weight = 1
        """

        if record["priority"] > WEAK_WORD_THRESHOLD:

            return WEAK_WORD_WEIGHT

        return 1

    # --------------------------------------------------------
    # SELECT NEXT VOCABULARY
    # --------------------------------------------------------

    def select_next_vocabulary(self):
        """
        Selects the next vocabulary item.

        Step 1:
            Find vocabulary that is due.

        Step 2:
            Give weak vocabulary five times the selection weight.

        Step 3:
            Randomly select one vocabulary item.

        If no vocabulary is currently due, the earliest scheduled
        vocabulary is returned so the application remains usable
        during testing.
        """

        records = list(
            self.load_vocabulary()
        )

        if not records:

            return None

        due_records = [
            record
            for record in records
            if self.is_due(record)
        ]

        # ----------------------------------------------------
        # IF NO WORD IS DUE
        # ----------------------------------------------------

        if not due_records:

            return min(
                records,
                key=lambda record:
                    self._review_datetime(
                        record["next_review"]
                    ) or self._now()
            )

        # ----------------------------------------------------
        # WEIGHTED RANDOM SELECTION
        # ----------------------------------------------------

        weights = [
            self.calculate_weight(record)
            for record in due_records
        ]

        return random.choices(
            due_records,
            weights=weights,
            k=1
        )[0]

    # --------------------------------------------------------
    # FIND WEAK VOCABULARY
    # --------------------------------------------------------

    def weak_vocabulary(self):
        """
        Returns vocabulary with priority greater than 10.
        """

        records = self.load_vocabulary()

        return [
            record
            for record in records
            if record["priority"] > WEAK_WORD_THRESHOLD
        ]

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    def statistics(self):
        """
        Calculates overall vocabulary-learning statistics.

        Returns:
            total vocabulary
            total attempts
            total correct answers
            accuracy percentage
        """

        records = self.load_vocabulary()

        total_vocabulary = len(records)

        total_attempts = sum(
            record["attempts"]
            for record in records
        )

        total_correct = sum(
            record["correct_count"]
            for record in records
        )

        if total_attempts == 0:

            accuracy = 0.0

        else:

            accuracy = (
                total_correct
                / total_attempts
                * 100
            )

        return (
            total_vocabulary,
            total_attempts,
            total_correct,
            accuracy
        )


# ============================================================
# DISPLAY FUNCTIONS
# ============================================================

def display_statistics(vocabulary):
    """
    Displays the user's overall learning statistics.
    """

    (
        total,
        attempts,
        correct,
        accuracy
    ) = vocabulary.statistics()

    print("\n==============================")
    print("        STATISTICS")
    print("==============================")

    print(
        f"Total vocabulary: {total}"
    )

    print(
        f"Total attempts: {attempts}"
    )

    print(
        f"Correct answers: {correct}"
    )

    print(
        f"Overall accuracy: {accuracy:.2f}%"
    )

    print("==============================")


def display_weak_vocabulary(vocabulary):
    """
    Displays vocabulary classified as high priority.
    """

    weak_words = vocabulary.weak_vocabulary()

    print("\n==============================")
    print("      HIGH-PRIORITY WORDS")
    print("==============================")

    if not weak_words:

        print("No high-priority vocabulary.")

        return

    for record in weak_words:

        print(
            f"{record['word']} | "
            f"priority: {record['priority']} | "
            f"interval: {record['interval_days']} days"
        )

    print("==============================")


# ============================================================
# PRACTICE SESSION
# ============================================================

def run_practice(vocabulary):
    """
    Runs the terminal vocabulary practice session.
    """

    if not vocabulary.load_vocabulary():

        print(
            "The vocabulary database is empty."
        )

        return

    print("\n===================================")
    print("       VOCABULARY PRACTICE")
    print("===================================")

    print(
        "Y = correct"
        " | N = incorrect"
        " | S = statistics"
        " | M = high-priority"
        " | E = exit"
    )

    print("===================================")

    while True:

        # ----------------------------------------------------
        # SELECT NEXT WORD
        # ----------------------------------------------------

        record = (
            vocabulary.select_next_vocabulary()
        )

        if record is None:

            print(
                "No vocabulary is available."
            )

            return

        # ----------------------------------------------------
        # DISPLAY WORD
        # ----------------------------------------------------

        print(
            f"\nWord: {record['word']}"
        )

        print(
            f"Current priority: "
            f"{record['priority']}"
        )

        print(
            f"Current interval: "
            f"{record['interval_days']} days"
        )

        # ----------------------------------------------------
        # USER INPUT
        # ----------------------------------------------------

        answer = input(
            "Answer [Y/N/S/M/E]: "
        ).strip().lower()

        # ----------------------------------------------------
        # EXIT
        # ----------------------------------------------------

        if answer in {"e", "exit"}:

            print(
                "\nPractice ended."
            )

            display_statistics(
                vocabulary
            )

            return

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        if answer in {
            "s",
            "statistics"
        }:

            display_statistics(
                vocabulary
            )

            continue

        # ----------------------------------------------------
        # HIGH-PRIORITY VOCABULARY
        # ----------------------------------------------------

        if answer in {
            "m",
            "mistakes",
            "weak"
        }:

            display_weak_vocabulary(
                vocabulary
            )

            continue

        # ----------------------------------------------------
        # INVALID ANSWER
        # ----------------------------------------------------

        if answer not in {
            "y",
            "yes",
            "n",
            "no"
        }:

            print(
                "Invalid input. "
                "Use Y, N, S, M, or E."
            )

            continue

        # ----------------------------------------------------
        # UPDATE DATABASE
        # ----------------------------------------------------

        updates = vocabulary.process_answer(
            record,
            answer
        )

        # ----------------------------------------------------
        # DISPLAY RESULT
        # ----------------------------------------------------

        if answer in {
            "y",
            "yes"
        }:

            print("\nCorrect!")

        else:

            print("\nIncorrect.")

            print(
                f"Meaning: {record['meaning']}"
            )

        print(
            f"New priority: "
            f"{updates['priority']}"
        )

        print(
            f"New interval: "
            f"{updates['interval_days']} days"
        )

        print(
            f"Next review: "
            f"{updates['next_review']}"
        )


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        vocabulary = VocabularyDatabase()

        run_practice(
            vocabulary
        )

    except RuntimeError as error:

        print(
            f"Database error: {error}"
        )

    except sqlite3.Error as error:

        print(
            f"SQLite error: {error}"
        )