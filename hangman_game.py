import secrets
from hangman_words import words
import time
from AES import authentication
import string
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.theme import Theme
from rich.text import Text
from database import load_scores, save_score
 
console = Console(theme=Theme({"prompt": "#C8A2C8"}))

def num_of_spaces(word):
    return word.count(" ")

def ask_menu_choice(prompt, choices):
    choices_text = "/".join(choices)
    while True:
        choice = console.input(
            f"[bold yellow]{prompt}[/bold yellow] "
            f"[bold #E6B3FF][{choices_text}][/bold #E6B3FF]: "
        ).strip()
        if choice in choices:
            return choice
        console.print()
        console.print("[bold red]Please choose one of the displayed options.[/bold red]")
        console.print()

hangman_art = {0: ("  ", "  ", "  "), 
               1: (" o ", "  ", "  "),
               2: (" o ", " | ", "  "),
               3: (" o ", "/| ", "  "),
               4: (" o ", "/|\\ ", "  "),
               5: (" o ", "/|\\ ", "/ "),
               6: (" o ", "/|\\ ", "/ \\")}

def display_man(wrong_guesses):
    for part in hangman_art[wrong_guesses]:
        console.print(Text(part, style="bright_green"))

def display_hint(hint):
    console.print(" ".join(f"[bold cyan]{character}[/bold cyan]" for character in hint))

def death():
    print()
    console.print(Text(" |/ ", style="orange1"))
    console.print(Text(" |\\ ", style="orange1"))
    time.sleep(1)  
    console.print(Text(" ___ ", style="orange1"))
    console.print(Text("|   |", style="orange1"))
    console.print(Text("|___|", style="orange1"))

def display_game_info():
    console.print(
        Panel(
            "[bold cyan]Welcome to Hangman![/bold cyan]\n"
            "Try to guess the word by suggesting letters.\n"
            "You have 6 attempts to guess wrong letters before you lose.\n"
            "Your score increases based on the number of spaces in the word.\n\n"
            "[yellow]Good luck![/yellow]",
            title="[bold]GAME INFO[/bold]",
            border_style="cyan",
        )
    )

def sign_out(username):
    console.print(f"[cyan]Goodbye, [bold yellow]{username}[/bold yellow]! Signing out...[/cyan]")
    return True


def play_hangman(username):

    while True:

        scores = load_scores()
        user_data = scores.get(username, {
            "score": 0,
            "guessed_words": [],
            "wins": 0,
            "losses": 0,
        })
        user_score = user_data.get("score", 0)
        guessed_words = user_data.get("guessed_words", [])
        guessed_words_lower = [w.lower() for w in guessed_words]
        words_pool_lower = list(set([w.lower() for w in words])) # removes duplicates
        
        # Word pool guard check
        if len(guessed_words_lower) >= len(words_pool_lower):
            console.print(Panel("[bold green]You have guessed all the words, congratulations![/bold green]", border_style="green"))
            console.print("[dim]Returning to main menu...[/dim]")
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
            guess = Prompt.ask("[bold yellow]Guess a letter[/bold yellow]").lower()
            
            if len(guess) != 1:
                console.print("[yellow]One letter at a time.[/yellow]")
                continue

            if guess not in string.ascii_letters:
                console.print("[yellow]Only letters.[/yellow]")
                continue

            if guess in guessed_letters:
                console.print("[yellow]You already guessed that letter.[/yellow]")
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
                updated_scores = load_scores()
                updated_user = updated_scores[username]
                console.print(f"[bold]Your score is:[/bold] {updated_user['score']}")
                console.print(f"[green]Wins:[/green] {updated_user['wins']} | [red]Losses:[/red] {updated_user['losses']}")

                console.print(Panel(f"[bold red]You lost![/bold red]\nThe word was [yellow]{answer}[/yellow]", title="GAME OVER", border_style="red"))
                again = Prompt.ask("Play again?", choices=["y", "n"], default="n").lower()
                if again == "y":
                    break  
                else:
                    console.print("[dim]Returning to main menu...[/dim]")
                    return 

            if "_" not in hint:
                console.print(Panel(f"[bold green]You won![/bold green]\nThe word was [cyan]{answer}[/cyan]", title="SUCCESS", border_style="green"))

                gained_points = num_of_spaces(answer) + 1   
                save_score(username, gained_points, answer)
                
                updated_scores = load_scores()
                updated_user = updated_scores[username]
                console.print(f"[bold]Your score is:[/bold] {updated_user['score']}")
                console.print(f"[green]Wins:[/green] {updated_user['wins']} | [red]Losses:[/red] {updated_user['losses']}")

                again = Prompt.ask("Play again?", choices=["y", "n"], default="n").lower()
                if again == "y":
                    break  
                else:
                    console.print("[dim]Returning to main menu...[/dim]")
                    return       

def main(username):

    while True:
        console.print(Panel(
            "[cyan]0[/cyan] - Game info\n"
            "[cyan]1[/cyan] - Play Hangman\n"
            "[cyan]2[/cyan] - View Scoreboard\n"
            "[cyan]3[/cyan] - Your guessed words\n"
            "[cyan]4[/cyan] - Exit\n"
            "[cyan]5[/cyan] - Sign Out",
            title="[bold]MAIN MENU[/bold]",
            border_style="blue",
        ))
        choice = ask_menu_choice("Enter your choice", ["0", "1", "2", "3", "4", "5"])

        if choice == "0":
            display_game_info()

        elif choice == "1":
            play_hangman(username)

        elif choice == "2":
            scores = load_scores()
            if not scores:
                console.print("[yellow]No scores available.[/yellow]")
            else:
                compiled_scores = []
                for user, data in scores.items():
                    if isinstance(data, dict):
                        score = data.get("score", 0)
                        wins = data.get("wins", 0)
                        losses = data.get("losses", 0)
                    else:
                        score = data
                        wins = 0
                        losses = 0

                    total_games = wins + losses
                    win_ratio = wins / total_games if total_games else 0
                    compiled_scores.append((user, score, win_ratio))

                compiled_scores.sort(key=lambda item: (item[1], item[2]), reverse=True)

                table = Table(title="SCOREBOARD", border_style = "cyan")
                table.add_column("Rank", style = "yellow", justify = "center")
                table.add_column("User", style = "cyan")
                table.add_column("Score", style = "green", justify = "right")
                table.add_column("Wins", style = "green", justify = "right")
                table.add_column("Losses", style = "red", justify = "right")
                table.add_column("Win Ratio", justify = "right")
                table.add_column("Total Games", style = "yellow", justify = "right")


                for rank, (user, score, win_ratio) in enumerate(compiled_scores, start=1):
                    user_data = scores[user]
                    wins = user_data.get("wins", 0) if isinstance(user_data, dict) else 0
                    losses = user_data.get("losses", 0) if isinstance(user_data, dict) else 0
                    total_games = user_data.get("total_games", wins + losses) if isinstance(user_data, dict) else 0
                    display_user = f"[bold yellow]{user}[/bold yellow]" if user == username else user

                    if win_ratio <= 0.20:
                        win_ratio_style = "bold red"
                    elif win_ratio > 0.20 and win_ratio <= 0.40:
                        win_ratio_style = "orange_red1"
                    elif win_ratio > 0.40 and win_ratio <= 0.60:
                        win_ratio_style = "bright_yellow"
                    elif win_ratio > 0.60 and win_ratio <= 0.80:
                        win_ratio_style = "bright_green"
                    else:
                        win_ratio_style = "magenta"

                    table.add_row(
                        str(rank),
                        display_user,
                        str(score),
                        str(wins),
                        str(losses),
                        f"[{win_ratio_style}]{win_ratio:.1%}[/{win_ratio_style}]",
                        str(total_games),
                    )

                console.print(table)

        elif choice == "3":
            scores = load_scores()
            user_data = scores.get(username, {})

            if isinstance(user_data, dict):
                history = user_data.get("guessed_words", [])
            else:
                history = []
            
            if not history:
                console.print("[yellow]No words have been guessed so far.[/yellow]")
            else:
                console.print(Panel(", ".join(history), title="GUESSED WORDS", border_style="cyan"))

        elif choice == "4":
            console.print("[bold cyan]Thanks for using the program.[/bold cyan]")
            return False

        elif choice == "5":
            if sign_out(username):
                return True

        else:
            console.print("[bold red]Invalid choice, please try again.[/bold red]")



if __name__ == "__main__":
    while True:
        user = authentication()
        if not user:
            break

        should_continue = main(user)
        if not should_continue:
            break
