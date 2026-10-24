from GUI import VocabularyGUI
from database import VocabularyDatabase

if __name__ == "__main__":
    database = VocabularyDatabase()
    VocabularyGUI().mainloop()
