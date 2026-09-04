import secrets
from hangman_words import words
import time
from AES import authentication
import json
import os
 
SCORES_FILE = "scores.json"

def num_of_spaces(word):
    return word.count(" ")

def load_scores():
    if os.path.exists(SCORES_FILE):
        with open(SCORES_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    return {}

def save_score(username, points, answer):
    scores = load_scores()
    
    if username not in scores or not isinstance(scores[username], dict):
        scores[username] = {"score": 0, "guessed_words": []}

    scores[username]["score"] += points

    if points > 0 and answer not in scores[username]["guessed_words"]:
        scores[username]["guessed_words"].append(answer)

    print(f"Guessed words history for {username}: {scores[username]['guessed_words']}")

    with open(SCORES_FILE, "w") as file:
        json.dump(scores, file, indent=4)

hangman_art = {0: ("  ", "  ", "  "), 
               1: (" o ", "  ", "  "),
               2: (" o ", " | ", "  "),
               3: (" o ", "/| ", "  "),
               4: (" o ", "/|\\ ", "  "),
               5: (" o ", "/|\\ ", "/ "),
               6: (" o ", "/|\\ ", "/ \\")}

def display_man(wrong_guesses):
    for part in hangman_art[wrong_guesses]:
        print(part)

def display_hint(hint):
    print(" ".join(hint))

def death():
    print(" |/ ")
    print(" |\\ ")
    time.sleep(1)  
    print(" ___ ")
    print("|   |")
    print("|___|")

def display_game_info():
    print("\n--- GAME INFO ---")
    print("Welcome to Hangman!")
    print("Try to guess the word by suggesting letters.")
    print("You have 6 attempts to guess wrong letters before you lose.")
    print("Your score increases based on the number of spaces in the word.")
    print("Good luck!\n")

def play_hangman(username):

    while True:
        scores = load_scores()
        user_data = scores.get(username, {"score": 0, "guessed_words": []})
        user_score = user_data.get("score", 0)
        guessed_words = user_data.get("guessed_words", [])
        guessed_words_lower = [w.lower() for w in guessed_words]
        words_pool_lower = list(set([w.lower() for w in words])) # removes duplicates
        
        # Word pool guard check
        if len(guessed_words_lower) >= len(words_pool_lower):
            print("\nYou have guessed all the words, congratulations!")
            print("Returning to main menu...")
            return  
        

        while True:
            answer = secrets.choice(words_pool_lower) 
            if answer not in guessed_words_lower:
                break

        hint = [char if char in [" ", "'", '"', "-"] else "_" for char in answer]
        wrong_guesses = 0
        guessed_letters = set()

        while True:
            display_man(wrong_guesses)
            display_hint(hint)
            guess = input("guess a letter: ").lower()
            
            if len(guess) != 1:
                print("one letter at a time")
                continue

            if guess in guessed_letters:
                print("you already guessed that letter")
                continue
            guessed_letters.add(guess)

            if guess in answer:
                for i in range(len(answer)):
                    if answer[i] == guess:
                        hint[i] = guess
            else: 
                wrong_guesses += 1

            if wrong_guesses == 6:
                display_man(wrong_guesses)
                death()
                save_score(username, 0, answer)  
                print(f"your score is {user_score}")

                again = input(f"you lost, the word was {answer}, play again? (y/n): ").lower()
                if again == "y":
                    break  
                else:
                    print("Returning to main menu...")
                    return 

            if "_" not in hint:
                print(f"you won, the word was {answer}")

                gained_points = num_of_spaces(answer) + 1   
                save_score(username, gained_points, answer)
                
                updated_scores = load_scores()
                print(f"your score is {updated_scores[username]['score']}")

                again = input(f"the word was {answer}, play again? (y/n): ").lower()
                if again == "y":
                    break  
                else:
                    print("Returning to main menu...")
                    return       

def main(username):
    print(f"Welcome, {username}!")

    while True:
        print("\nMENU: 0 - Game info, 1 - Play Hangman, 2 - View Scoreboard, 3 - Your guessed words, 4 - Exit")
        choice = input("Enter your choice (0-4): ").strip()

        if choice == "0":
            display_game_info()

        elif choice == "1":
            play_hangman(username)

        elif choice == "2":
            scores = load_scores()
            if not scores:
                print("No scores available.")
            else:
                print("\n--- Scoreboard ---")
                compiled_scores = []
                for user, data in scores.items():
                    if isinstance(data, dict):
                        score = data.get("score", 0)
                    else:
                        score = data

                    compiled_scores.append((user, score))

                compiled_scores.sort(key=lambda item: item[1], reverse=True)

                for user, score in compiled_scores:
                    print(f"{user}: {score} points")

        elif choice == "3":
            scores = load_scores()
            user_data = scores.get(username, {})

            if isinstance(user_data, dict):
                history = user_data.get("guessed_words", [])
            else:
                history = []
            
            if not history:
                print("No words have been guessed so far")
            else:
                print("\n--- Guessed words ---")
                print(", ".join(history))

        elif choice == "4":
            print("Thanks for using the program")
            break
        else:
            print("Invalid choice, please try again")

if __name__ == "__main__":
    user = authentication()
    if user:
        main(user)
