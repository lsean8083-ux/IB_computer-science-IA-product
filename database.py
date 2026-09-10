"""SQLite persistence layer for the Trial_3 vocabulary application."""
import csv
import random
import sqlite3
from datetime import datetime
from pathlib import Path

from algorithm import HIGH_PRIORITY_THRESHOLD, calculate_update, selection_weight

DATABASE_PATH = Path(__file__).with_name("Vocabulary_list_Trial_3.db")


class VocabularyDatabase:
    """Owns SQLite storage; each operation uses parameterized SQL."""
    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = str(database_path)
        self._create_schema()

    def _connect(self):
        try:
            connection = sqlite3.connect(self.database_path)
            connection.row_factory = sqlite3.Row
            return connection
        except sqlite3.Error as error:
            raise RuntimeError(f"Could not connect to vocabulary database: {error}") from error

    def _create_schema(self):
        with self._connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS words (
                  word TEXT PRIMARY KEY COLLATE NOCASE, meaning TEXT NOT NULL,
                  priority INTEGER NOT NULL DEFAULT 0, interval_days REAL NOT NULL DEFAULT 1,
                  next_review TEXT NOT NULL, correct_streak INTEGER NOT NULL DEFAULT 0,
                  attempts INTEGER NOT NULL DEFAULT 0, correct_count INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS idx_words_word ON words(word);
                CREATE INDEX IF NOT EXISTS idx_words_review ON words(next_review);
                CREATE TABLE IF NOT EXISTS daily_answers (
                  answer_id INTEGER PRIMARY KEY, word TEXT NOT NULL, answer_date TEXT NOT NULL,
                  answered_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_daily_answers_date ON daily_answers(answer_date);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)

    @staticmethod
    def _now(): return datetime.now()

    def add_word(self, word, meaning):
        word, meaning = word.strip(), meaning.strip()
        if not word or not meaning: raise ValueError("Word and meaning are required.")
        try:
            with self._connect() as con:
                con.execute("INSERT INTO words VALUES (?, ?, 0, 1, ?, 0, 0, 0)",
                            (word, meaning, self._now().isoformat(timespec="seconds")))
        except sqlite3.IntegrityError as error:
            raise ValueError("That vocabulary word already exists.") from error

    def get_word(self, word):
        with self._connect() as con:
            return con.execute("SELECT * FROM words WHERE word = ?", (word,)).fetchone()

    def search(self, query, limit=100):
        with self._connect() as con:
            return con.execute("SELECT * FROM words WHERE word LIKE ? ORDER BY word LIMIT ?",
                               (f"%{query.strip()}%", limit)).fetchall()

    def all_words(self, limit=None):
        sql = "SELECT * FROM words ORDER BY word" + (" LIMIT ?" if limit else "")
        with self._connect() as con: return con.execute(sql, (limit,) if limit else ()).fetchall()

    def delete_word(self, word):
        with self._connect() as con: con.execute("DELETE FROM words WHERE word = ?", (word,))

    def high_priority(self):
        with self._connect() as con:
            return con.execute("SELECT * FROM words WHERE priority > ? ORDER BY priority DESC, word",
                               (HIGH_PRIORITY_THRESHOLD,)).fetchall()

    def review_list(self, count=50, current_time=None):
        """Efficient weighted selection from due words; 5x for priority > 10."""
        if not 1 <= count <= 50: raise ValueError("Review-list size must be 1–50.")
        now = (current_time or self._now()).isoformat(timespec="seconds")
        with self._connect() as con:
            rows = con.execute("SELECT * FROM words WHERE next_review <= ?", (now,)).fetchall()
            if not rows: rows = con.execute("SELECT * FROM words ORDER BY next_review LIMIT ?", (count,)).fetchall()
        if not rows: return []
        # Weighted selection without replacement creates a genuine custom set
        # of up to 50 different vocabulary items.  High-priority records still
        # have the explicit five-times chance at every selection step.
        selected = []
        available = list(rows)
        while available and len(selected) < count:
            choice = random.choices(available, weights=[selection_weight(row) for row in available], k=1)[0]
            selected.append(choice)
            available.remove(choice)
        return selected

    def select_next_vocabulary(self):
        choices = self.review_list(1)
        return choices[0] if choices else None

    def process_answer(self, record, answer, current_time=None):
        updates = calculate_update(record, answer, current_time)
        now = current_time or self._now()
        with self._connect() as con:
            con.execute("""UPDATE words SET priority=?, interval_days=?, next_review=?, correct_streak=?,
                        attempts=?, correct_count=? WHERE word=?""",
                        (updates["priority"], updates["interval_days"], updates["next_review"],
                         updates["correct_streak"], updates["attempts"], updates["correct_count"], record["word"]))
            con.execute("INSERT INTO daily_answers(word, answer_date, answered_at) VALUES (?, ?, ?)",
                        (record["word"], now.date().isoformat(), now.isoformat(timespec="seconds")))
        return updates

    def statistics(self):
        with self._connect() as con:
            row = con.execute("SELECT COUNT(*) total, COALESCE(SUM(attempts),0) attempts, COALESCE(SUM(correct_count),0) correct, COALESCE(SUM(priority > ?),0) high FROM words", (HIGH_PRIORITY_THRESHOLD,)).fetchone()
        return dict(row) | {"accuracy": (row["correct"] / row["attempts"] * 100) if row["attempts"] else 0.0}

    def get_daily_goal(self):
        with self._connect() as con:
            row = con.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()
        return int(row["value"]) if row else 20

    def set_daily_goal(self, goal):
        if not 1 <= int(goal) <= 200: raise ValueError("Daily goal must be between 1 and 200.")
        with self._connect() as con: con.execute("INSERT OR REPLACE INTO settings VALUES ('daily_goal', ?)", (str(goal),))

    def today_progress(self, current_time=None):
        day = (current_time or self._now()).date().isoformat()
        with self._connect() as con: return con.execute("SELECT COUNT(*) FROM daily_answers WHERE answer_date=?", (day,)).fetchone()[0]

    def import_csv(self, path):
        added = 0
        with open(path, newline="", encoding="utf-8-sig") as file:
            for row in csv.DictReader(file):
                try: self.add_word(row.get("word", ""), row.get("meaning", "")); added += 1
                except ValueError: pass
        return added

    def export_csv(self, path):
        with open(path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["word", "meaning", "priority", "interval_days", "next_review", "correct_streak", "attempts", "correct_count"])
            writer.writeheader(); writer.writerows(map(dict, self.all_words()))

    def migrate_trial_2(self, old_path=None):
        old_path = Path(old_path or Path(__file__).with_name("Vocabulary_list_Trial_2.db"))
        if not old_path.exists(): return 0
        try:
            source = sqlite3.connect(old_path); source.row_factory = sqlite3.Row
            rows = source.execute("SELECT * FROM words").fetchall(); source.close(); added = 0
            for row in rows:
                try:
                    with self._connect() as con:
                        con.execute("INSERT INTO words VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tuple(row[key] for key in ("word","meaning","priority","interval_days","next_review","correct_streak","attempts","correct_count")))
                    added += 1
                except sqlite3.IntegrityError: pass
            return added
        except sqlite3.Error as error: raise RuntimeError(f"Migration failed: {error}") from error
