"""Tkinter interface for Trial 3.  Start it with ``python Trial_3.py``."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ai_generator import ContextPassageGenerator
from database import VocabularyDatabase

BACKGROUND = "#ffffff"
PANEL = "#ffffff"
TEXT = "#000000"
ACCENT = "#e6e6e6"
GREEN = "#dcefd9"
RED = "#f5dada"


class VocabularyGUI(tk.Tk):
    """Main application window. Only one page is ever displayed at a time."""

    def __init__(self):
        super().__init__()
        self.title("Adaptive Vocabulary Learning")
        self.geometry("800x560")
        self.minsize(680, 480)
        self.configure(bg=BACKGROUND)
        self._configure_progress_bar()
        try:
            self.database = VocabularyDatabase()
        except RuntimeError as error:
            messagebox.showerror("Database error", str(error), parent=self)
            self.destroy()
            return

        self.surface = None
        self.content = None
        self._create_page_surface()
        self.timer_id = None
        self.current_record = None
        self.session_words = []
        self.review_queue = []
        self.mode = None
        self.reviewed = self.known = self.unknown = 0
        self.remaining_seconds = 0
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.show_home()

    def _configure_progress_bar(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Vocabulary.Horizontal.TProgressbar", troughcolor="#eeeeee",
                        background=GREEN, bordercolor="#eeeeee", lightcolor=GREEN,
                        darkcolor=GREEN)

    def _clear_page(self):
        """Cancel the timer and replace the complete page surface.

        Recreating the surface, rather than only destroying its child widgets,
        forces a full repaint in the macOS Tk build used by this project.
        """
        if self.timer_id is not None:
            self.after_cancel(self.timer_id)
            self.timer_id = None
        self.unbind("<y>")
        self.unbind("<n>")
        if self.surface is not None and self.surface.winfo_exists():
            self.surface.destroy()
        self._create_page_surface()
        self.update_idletasks()

    def _create_page_surface(self):
        """Create an opaque canvas so macOS receives a full repaint request."""
        self.surface = tk.Canvas(self, bg=BACKGROUND, highlightthickness=0, bd=0)
        self.surface.pack(fill="both", expand=True)
        self.content = tk.Frame(self.surface, bg=BACKGROUND)
        self._content_window = self.surface.create_window(0, 0, anchor="nw", window=self.content)
        self.surface.bind("<Configure>", self._resize_page_surface)

    def _resize_page_surface(self, event):
        """Keep the canvas-backed page opaque across the complete window."""
        self.surface.itemconfigure(self._content_window, width=event.width, height=event.height)

    def _label(self, parent, text="", **options):
        options.setdefault("bg", BACKGROUND)
        options.setdefault("fg", TEXT)
        return tk.Label(parent, text=text, **options)

    def _button(self, parent, text, command, colour=ACCENT, **options):
        options.setdefault("bg", colour)
        options.setdefault("fg", TEXT)
        options.setdefault("activebackground", colour)
        options.setdefault("activeforeground", TEXT)
        options.setdefault("font", ("Arial", 12, "bold"))
        options.setdefault("relief", "raised")
        options.setdefault("bd", 2)
        options.setdefault("cursor", "hand2")
        return tk.Button(parent, text=text, command=command, **options)

    def show_home(self):
        self._clear_page()
        page = tk.Frame(self.content, bg=BACKGROUND)
        page.pack(fill="both", expand=True, padx=28, pady=26)
        self._label(page, "Adaptive Vocabulary Learning", font=("Arial", 25, "bold")).pack(pady=(0, 7))
        self._label(page, "Y = Yes, I know     •     N = No, I don't know", font=("Arial", 12)).pack(pady=(0, 22))

        grid = tk.Frame(page, bg=BACKGROUND)
        grid.pack()
        actions = [
            ("Mode A: Intensive Review", self.show_mode_a_setup),
            ("Mode B: Daily Goal", self.start_mode_b),
            ("Set Daily Goal", self.show_daily_goal),
            ("Add Vocabulary", self.show_add_vocabulary),
            ("Search Vocabulary", self.show_search),
            ("High-Priority Vocabulary", self.show_high_priority),
            ("Statistics", self.show_statistics),
            ("AI Context Passage", self.show_ai_passage),
            ("API Key Insertion", self.show_api_key_insertion),
            ("CSV Import / Export", self.show_csv_tools),
            ("Exit", self._close),
        ]
        for number, (title, callback) in enumerate(actions):
            button = self._button(grid, title, callback, width=28)
            button.grid(row=number // 2, column=number % 2, padx=9, pady=7, ipady=3)

    # ----- Practice modes -------------------------------------------------
    def show_mode_a_setup(self):
        window = self._dialog("Mode A — Intensive Review")
        minutes = tk.IntVar(value=5)
        set_size = tk.IntVar(value=10)
        self._label(window, "Timed, intensive vocabulary review", font=("Arial", 16, "bold")).pack(pady=(0, 15))
        self._label(window, "Timer (minutes):").pack()
        tk.OptionMenu(window, minutes, 5, 10, 15).pack()
        self._label(window, "Vocabulary set size (10–50):").pack(pady=(12, 0))
        tk.Spinbox(window, from_=10, to=50, textvariable=set_size, width=8).pack()

        def begin():
            if not 10 <= set_size.get() <= 50:
                messagebox.showerror("Invalid vocabulary set", "Choose between 10 and 50 vocabulary items.", parent=window.winfo_toplevel())
                return
            window.winfo_toplevel().destroy()
            self.start_session("A", set_size.get(), minutes.get() * 60)

        self._button(window, "Start Mode A", begin).pack(pady=18)

    def start_mode_b(self):
        self.start_session("B", self.database.get_daily_goal(), 0)

    def start_session(self, mode, set_size, seconds):
        self._clear_page()
        self.mode = mode
        self.session_words = self.database.review_list(set_size)
        self.review_queue = list(self.session_words)
        self.remaining_seconds = seconds
        self.reviewed = self.known = self.unknown = 0

        page = tk.Frame(self.content, bg=BACKGROUND)
        page.pack(fill="both", expand=True, padx=30, pady=24)
        self.session_heading = self._label(page, font=("Arial", 20, "bold"))
        self.session_heading.pack()
        self.progress_bar = ttk.Progressbar(page, length=450, style="Vocabulary.Horizontal.TProgressbar", maximum=100)
        self.progress_bar.pack(pady=(14, 5))
        self.progress_text = self._label(page, font=("Arial", 12))
        self.progress_text.pack()
        self.word_label = self._label(page, font=("Arial", 34, "bold"), wraplength=650)
        self.word_label.pack(pady=(46, 9))
        self.meaning_label = self._label(page, font=("Arial", 16), wraplength=650, justify="center")
        self.meaning_label.pack()
        answers = tk.Frame(page, bg=BACKGROUND)
        answers.pack(pady=30)
        self.y_button = self._button(answers, "Y — Yes, I know", lambda: self.submit_answer("y"), GREEN, width=20)
        self.y_button.grid(row=0, column=0, padx=8, ipady=4)
        self.n_button = self._button(answers, "N — No, I don't know", lambda: self.submit_answer("n"), RED, width=20)
        self.n_button.grid(row=0, column=1, padx=8, ipady=4)
        self._button(page, "End session", self.finish_session, colour=ACCENT).pack()
        self.bind("<y>", lambda event: self.submit_answer("y"))
        self.bind("<n>", lambda event: self.submit_answer("n"))
        self.show_next_question()
        if seconds:
            self._timer_tick()

    def _timer_tick(self):
        if self.remaining_seconds <= 0:
            self.finish_session()
            return
        self.remaining_seconds -= 1
        self.refresh_session_status()
        self.timer_id = self.after(1000, self._timer_tick)

    def refresh_session_status(self):
        if self.mode == "A":
            minutes, seconds = divmod(self.remaining_seconds, 60)
            self.session_heading.config(text=f"Mode A — {minutes:02d}:{seconds:02d} remaining")
            self.progress_bar["value"] = 0
            self.progress_text.config(text=f"Words reviewed this session: {self.reviewed}")
        else:
            goal = self.database.get_daily_goal()
            completed = self.database.today_progress()
            percentage = min(100, completed / goal * 100)
            self.session_heading.config(text="Mode B — Daily Goal")
            self.progress_bar["value"] = percentage
            suffix = " — Goal Completed" if completed >= goal else ""
            self.progress_text.config(text=f"{completed} / {goal} completed ({percentage:.0f}%){suffix}")

    def show_next_question(self):
        if not self.review_queue:
            # Continue cycling only through the user's selected set in Mode A.
            self.review_queue = list(self.session_words) if self.session_words else []
        self.current_record = self.review_queue.pop(0) if self.review_queue else None
        self.refresh_session_status()
        if self.current_record is None:
            self.word_label.config(text="No vocabulary available")
            self.meaning_label.config(text="Use Add Vocabulary to create your first item.")
            self.y_button.config(state="disabled")
            self.n_button.config(state="disabled")
            return
        self.word_label.config(text=self.current_record["word"])
        self.meaning_label.config(text="Do you know this word?")
        self.y_button.config(state="normal")
        self.n_button.config(state="normal")

    def submit_answer(self, answer):
        if self.current_record is None or str(self.y_button["state"]) == "disabled":
            return
        try:
            self.database.process_answer(self.current_record, answer)
        except (RuntimeError, ValueError) as error:
            messagebox.showerror("Could not save answer", str(error), parent=self)
            return
        self.reviewed += 1
        self.known += answer == "y"
        self.unknown += answer == "n"
        self.meaning_label.config(text=f"Meaning: {self.current_record['meaning']}")
        self.y_button.config(state="disabled")
        self.n_button.config(state="disabled")
        self.after(850, self.show_next_question)

    def finish_session(self):
        self._clear_page()
        accuracy = self.known / self.reviewed * 100 if self.reviewed else 0
        messagebox.showinfo("Session complete", f"Words reviewed: {self.reviewed}\nYes, I know: {self.known}\nNo, I don't know: {self.unknown}\nSession accuracy: {accuracy:.1f}%", parent=self)
        self.show_home()

    # ----- Vocabulary management -----------------------------------------
    def show_daily_goal(self):
        window = self._dialog("Set Daily Goal")
        goal = tk.IntVar(value=self.database.get_daily_goal())
        self._label(window, "Daily vocabulary goal (1–200):").pack()
        tk.Spinbox(window, from_=1, to=200, textvariable=goal, width=8).pack(pady=8)

        def save():
            try:
                self.database.set_daily_goal(goal.get())
            except ValueError as error:
                messagebox.showerror("Invalid goal", str(error), parent=window.winfo_toplevel())
                return
            window.winfo_toplevel().destroy()
            messagebox.showinfo("Daily goal", "Daily goal saved.", parent=self)

        self._button(window, "Save goal", save).pack(pady=10)

    def show_add_vocabulary(self):
        window = self._dialog("Add Vocabulary")
        word, meaning = tk.StringVar(), tk.StringVar()
        self._entry(window, "Word", word)
        self._entry(window, "Meaning", meaning)

        def save():
            try:
                self.database.add_word(word.get(), meaning.get())
            except ValueError as error:
                messagebox.showerror("Could not add vocabulary", str(error), parent=window.winfo_toplevel())
                return
            word.set("")
            meaning.set("")
            messagebox.showinfo("Vocabulary added", "The word has been saved.", parent=window.winfo_toplevel())

        self._button(window, "Add word", save).pack(pady=12)

    def show_search(self):
        window = self._dialog("Search Vocabulary", size="650x420")
        query = tk.StringVar()
        self._entry(window, "Word or partial word", query)
        tree = self._tree(window)

        def search():
            tree.delete(*tree.get_children())
            for row in self.database.search(query.get()):
                tree.insert("", "end", values=(row["word"], row["meaning"], row["priority"]))

        self._button(window, "Search", search).pack(pady=8)

    def show_high_priority(self):
        window = self._dialog("High-Priority Vocabulary", size="650x420")
        self._label(window, "Priority above 10 (selected with 5× weight)", font=("Arial", 13, "bold")).pack()
        tree = self._tree(window)
        for row in self.database.high_priority():
            tree.insert("", "end", values=(row["word"], row["meaning"], row["priority"]))

    def show_statistics(self):
        statistics = self.database.statistics()
        window = self._dialog("Statistics")
        message = (f"Total vocabulary: {statistics['total']}\n\n"
                   f"Total attempts: {statistics['attempts']}\n\n"
                   f"Total correct answers: {statistics['correct']}\n\n"
                   f"Overall accuracy: {statistics['accuracy']:.2f}%\n\n"
                   f"High-priority words: {statistics['high']}")
        self._label(window, message, font=("Arial", 14), justify="left").pack(padx=25, pady=20)

    # ----- Optional import/export and AI ---------------------------------
    def show_csv_tools(self):
        window = self._dialog("CSV Import / Export")

        def import_file():
            path = filedialog.askopenfilename(parent=window.winfo_toplevel(), filetypes=[("CSV files", "*.csv")])
            if path:
                try:
                    count = self.database.import_csv(path)
                    messagebox.showinfo("Import complete", f"Added {count} new words.", parent=window.winfo_toplevel())
                except OSError as error:
                    messagebox.showerror("Import failed", str(error), parent=window.winfo_toplevel())

        def export_file():
            path = filedialog.asksaveasfilename(parent=window.winfo_toplevel(), defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
            if path:
                try:
                    self.database.export_csv(path)
                    messagebox.showinfo("Export complete", "Vocabulary exported.", parent=window.winfo_toplevel())
                except OSError as error:
                    messagebox.showerror("Export failed", str(error), parent=window.winfo_toplevel())

        self._button(window, "Import CSV (word, meaning)", import_file, width=28).pack(pady=9)
        self._button(window, "Export CSV", export_file, width=28).pack(pady=9)

    def show_ai_passage(self):
        window = self._dialog("AI Context Passage", size="700x560")
        self._label(window, "Select 3–8 target words.", font=("Arial", 13, "bold")).pack()
        words = self.database.high_priority() or self.database.all_words(50)
        word_box = tk.Listbox(window, selectmode="extended", height=9, width=45, bg=PANEL, fg=TEXT)
        word_box.pack(pady=8)
        for row in words:
            word_box.insert("end", row["word"])
        output = tk.Text(window, height=12, width=72, wrap="word", bg=PANEL, fg=TEXT)
        output.pack(padx=10, pady=8)

        def generate():
            targets = [word_box.get(index) for index in word_box.curselection()]
            try:
                passage, found = ContextPassageGenerator().generate(targets)
            except (ValueError, RuntimeError) as error:
                messagebox.showerror("AI passage", str(error), parent=window.winfo_toplevel())
                return
            output.delete("1.0", "end")
            output.insert("end", passage + f"\n\nValidated words ({len(found)}/{len(targets)}): " + ", ".join(found))

        self._button(window, "Generate passage", generate).pack(pady=(0, 10))

    def show_api_key_insertion(self):
        """Accept an API key for this running session without writing it to disk."""
        window = self._dialog("API Key Insertion", size="500x230")
        api_key = tk.StringVar(value=os.getenv("OPENAI_API_KEY", ""))
        self._label(window, "OpenAI API key", font=("Arial", 14, "bold")).pack(anchor="w")
        self._label(
            window,
            "The key is used only during this session. It is not stored in the database or source code.",
            wraplength=440,
            justify="left",
        ).pack(anchor="w", pady=(4, 12))
        tk.Entry(window, textvariable=api_key, show="•", bg=PANEL, fg=TEXT,
                 insertbackground=TEXT, width=52).pack(fill="x")

        def use_key():
            value = api_key.get().strip()
            if not value:
                messagebox.showerror("Missing API key", "Enter an API key before continuing.", parent=window.winfo_toplevel())
                return
            os.environ["OPENAI_API_KEY"] = value
            window.winfo_toplevel().destroy()
            messagebox.showinfo("API key added", "The key is ready for AI passage generation in this session.", parent=self)

        self._button(window, "Use API key for this session", use_key).pack(pady=16)

    # ----- Widget helpers -------------------------------------------------
    def _dialog(self, title, size="420x260"):
        top = tk.Toplevel(self)
        top.title(title)
        top.geometry(size)
        top.configure(bg=BACKGROUND)
        top.transient(self)
        frame = tk.Frame(top, bg=BACKGROUND)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        return frame

    def _entry(self, parent, title, variable):
        self._label(parent, title).pack(anchor="w")
        tk.Entry(parent, textvariable=variable, bg=PANEL, fg=TEXT, insertbackground=TEXT, width=45).pack(fill="x", pady=(0, 11))

    def _tree(self, parent):
        tree = ttk.Treeview(parent, columns=("word", "meaning", "priority"), show="headings", height=11)
        for name, width in (("word", 170), ("meaning", 320), ("priority", 80)):
            tree.heading(name, text=name.title())
            tree.column(name, width=width)
        tree.pack(fill="both", expand=True, pady=8)
        return tree

    def _close(self):
        self._clear_page()
        self.destroy()
