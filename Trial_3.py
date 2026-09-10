"""Main entry point. Run ``python Trial_3.py`` from this directory."""
from GUI import VocabularyGUI
from database import VocabularyDatabase

if __name__ == "__main__":
    database = VocabularyDatabase()
    try: database.migrate_trial_2()  # Never modifies the Trial_2 database.
    except RuntimeError: pass
    VocabularyGUI().mainloop()
