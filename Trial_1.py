import os
import sqlite3
import random
import sys
import tty
import termios

database_mode = "Vocabulary_list.db"

# online researched for terminal use:
def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, old_settings)

# main page

class Vocab_data:
    def __init__(self):
        self.database = database_mode
        self.data = []
        conn = sqlite3.connect(self.database)

        conn.close()

    def load(self):
        self.data = []
        conn = sqlite3.connect(self.database)
        for row in conn.execute('SELECT * FROM words'):
            word = row[0]
            meaning = row[1]
            priority = int(row[2])
            self.data.append([word, meaning, priority])
        conn.close()

        if self.data:
            random.shuffle(self.data)

    def save(self):
        conn = sqlite3.connect(self.database)
        conn.execute('DELETE FROM words')
        conn.executemany('INSERT INTO words VALUES (?,?,?)', self.data)
        conn.commit()
        conn.close()

    def show(self):
        for w in self.data:
            print(f"word：{w[0]}, meaning：{w[1]}, priority：{w[2]}")
        print("total number：", len(self.data))
        
    def show_mistake(self):
        for i in self.data:
            if i[2] > 0:
                print(i)
                
    def check(self):
        while True:
            answer = input(f"Detected that You have 20 wrongs on same vocabulary in the practice, do I need to lower down the difficulties? [\033[4mY\033[0mes] / [\033[4mN\033[0mo] ").lower()
            if answer == "yes" or answer == "y":
                os._exit(0) 
            elif answer == "no" or answer == "n":
                break
            else:
                print("error occured: please type your respond correctly")
                
    def get_next_word(self):
        weighted = []
        for item in self.data:
            p = item[2]
            if p == 0:
                weighted.append(item)
            elif p >= 3:
                weighted.extend([item]*8)
            elif p >= 10:
                weighted.extend([item]*12)
            else:
                weighted.extend([item]*18)
        return random.choice(weighted)

    def emergency_word(self):
        weighted = []
        for item in self.data:
            p = item[2]
            if p > 0:
                weighted.extend([item]*180)


    def test(self):

        if len(self.data) == 0:
            print("nothing left")
            return
        
        while True:
            word_item = self.get_next_word()
            print(f"Do you know this?  （ {word_item[0]} ）  ([\033[4mY\033[0mes]] / [\033[4mN\033[0mo]] / [\033[4mE\033[0mxit]] / [\033[4mS\033[0mcoreboard]])：") 
            answer = getch()
            
            if answer == "y" or answer == "yes":
                print("correct")
                if word_item[2] > 0:
                    word_item[2] -= 1
                print("priority：" + str(word_item[2]))
                
            elif answer == "e" or answer == "exit":
                print("exit successfully!")
                print("Test finished!")
                vocab.show_mistake()
                break
            elif answer == "s" or answer == "scoreboard":
                print("test result:")
                vocab.show_mistake()
                vocab.emergency_word()
                       
            else:
                word_item[2] += 1
                print("wrong")
                print("meaning：" + word_item[1])
                print("priority：" + str(word_item[2]))
                if word_item[2]> 20:
                    vocab.check()
                    
            self.save()


                

            


if __name__ == "__main__":
    
    
    
    vocab = Vocab_data()
    vocab.load()
    vocab.test()
    
    
