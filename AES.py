import os
from cryptography.fernet import Fernet
from getpass import getpass
import pyotp 
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.theme import Theme
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type
import keyring
from database import delete_user, load_data, save_data

console = Console(theme=Theme({"prompt": "#C8A2C8"}))

KEYRING_SERVICE = "HangmanGame"
KEYRING_USERNAME = "fernet-encryption-key"
LEGACY_KEY_FILE = "secret.key"


def load_secret_key():
    stored_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    if stored_key is not None:
        return stored_key.encode("ascii")

    if os.path.exists(LEGACY_KEY_FILE):
        with open(LEGACY_KEY_FILE, "rb") as file:
            secret_key = file.read()
    else:
        secret_key = Fernet.generate_key()

    keyring.set_password(
        KEYRING_SERVICE,
        KEYRING_USERNAME,
        secret_key.decode("ascii"),
    )

    if os.path.exists(LEGACY_KEY_FILE):
        os.remove(LEGACY_KEY_FILE)

    return secret_key


secret_key = load_secret_key()



password_hasher = PasswordHasher(
    time_cost = 3,
    memory_cost = 65536,
    parallelism = 4,
    hash_len = 32,
    salt_len = 16,
    type = Type.ID,
)


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(password, password_hash):
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False

def is_strong_password(password):
    special_chars = "!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~"
    return (len(password) >= 8 and 
            any(char.isdigit() for char in password) and 
            any(char.isalpha() for char in password) and 
            any(char.isupper() for char in password) and 
            any(char in special_chars for char in password))

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


# Main logic
def authentication():
    attempts = 0  
    cipher = Fernet(secret_key)  # Initialize cipher globally for convenience
    
    while attempts < 3:
        console.print(
            Panel(
                "[cyan]0[/cyan] - Forgotten Password\n"
                "[cyan]1[/cyan] - Register\n"
                "[cyan]2[/cyan] - Login\n"
                "[cyan]3[/cyan] - Delete Account\n"
                "[cyan]4[/cyan] - Exit",
                title=f"[bold cyan]AUTHENTICATION[/bold cyan] "
                f"[yellow](Attempts left: {3 - attempts})[/yellow]",
                border_style="cyan",
            )
        )
        choice = ask_menu_choice("Enter your choice", ["0", "1", "2", "3", "4"])

        if choice == "0":
            username = input("Enter your username: ").strip()
            data = load_data()

            user_record = next((user for user in data if user["username"] == username), None)

            if not user_record:
                print("User doesn't exist")
                continue

            # Legacy Guard Check
            if "totp_secret" not in user_record:
                print("This profile does not have 2FA recovery configured.")
                continue

            encrypted_secret = user_record["totp_secret"]
            decrypted_secret = cipher.decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")

            print("\n2FA Recovery")
            totp = pyotp.TOTP(decrypted_secret)
            user_code = input("Enter the current 6-digit code from your authenticator app: ").strip()

            if totp.verify(user_code, valid_window = 1): # valid_window allows time tolerance, +- 30 seconds
                print("\nVerification successful")

                while True:
                    new_password = getpass(prompt="Enter your new password: ", echo_char="*").strip()

                    if not is_strong_password(new_password):
                        print("At least 8 characters, at least one number, one uppercase letter, and special character")
                        continue

                    user_record["password"] = hash_password(new_password)
                    user_record.pop("salt", None)

                    save_data(data)

                    print("Password has been successfully reset, you can now login")
                    break
                
                attempts = 0
                continue
            else:
                print("Invalid 2FA code, please enter the correct code")
                attempts += 1

        elif choice == "1":
            username = input("Enter your username: ").strip()
            password = getpass(prompt="Enter your password: ", echo_char="*").strip()

            if not username or not password:
                print("Username / Password was left empty, please try again")
                continue

            data = load_data()
            user_exists = any(user["username"] == username for user in data)
            if user_exists:
                print("Username already exists, please try again")
                continue

            if not is_strong_password(password):
                print("At least 8 characters, at least one number, one uppercase letter, and special character")
                continue
                
            password_hash = hash_password(password)

            totp_secret = pyotp.random_base32()

            print("\n" + "="*50)
            print("SET UP TWO-FACTOR AUTHENTICATION")
            print(f"1. Open your authenticator app (e.g., Google Authenticator).")
            print(f"2. Add a new account manually using this secret key:")
            print(f"    {totp_secret}  ")
            input("Press Enter once you have saved/entered this key into your app...")

            registration_code = input("Enter the current 6-digit code from your authenticator app: ").strip()
            if not pyotp.TOTP(totp_secret).verify(registration_code, valid_window=1):
                print("Invalid 2FA code. Registration was canceled.")
                attempts += 1
                continue

            encrypted_totp = cipher.encrypt(totp_secret.encode("utf-8")).decode("utf-8")

            new_entry = {
                "username": username,
                "password": password_hash,
                "totp_secret": encrypted_totp  
            }

            data.append(new_entry)

            save_data(data)
            print("Registration was successful!")
            attempts = 0  

        elif choice == "2":
            username = input("Enter your username: ").strip()
            password = getpass(prompt="Enter your password: ", echo_char="*").strip()

            data = load_data()
            user_found = False
            password_correct = False
            saved_totp_secret = None

            for user in data:
                if user["username"] == username:
                    user_found = True
                    saved_totp_secret = user.get("totp_secret") 

                    password_correct = verify_password(password, user.get("password", ""))
                    break

            if user_found and password_correct:
                if not saved_totp_secret:
                    print("This profile does not have 2FA configured.")
                    attempts += 1
                    continue

                decrypted_secret = cipher.decrypt(saved_totp_secret.encode("utf-8")).decode("utf-8")
                totp = pyotp.TOTP(decrypted_secret)


                two_fa_attempts = 0
                while two_fa_attempts < 3:
                    print(f"\n--- 2FA VERIFICATION REQUIRED (Attempts left: {3 - two_fa_attempts}) ---")
                    user_code = input("Enter the 6-digit code from your authenticator app: ").strip()
                    
                    if totp.verify(user_code, valid_window = 1):
                        print(f"Login successful! Welcome, {username}.")
                        return username  # Successfully exits authentication and enters Hangman
                    else:
                        print("Invalid 2FA verification code.")

                        two_fa_attempts += 1
                
                attempts += 1
            else:
                print("Invalid password or username")
                attempts += 1  

        elif choice == "3":
            username = input("Enter your username: ").strip()
            password = getpass(prompt="Enter your password: ", echo_char="*").strip()
            data = load_data()

            matching_user = next((user for user in data if user.get("username") == username), None)

            if matching_user is None:
                print("User doesn't exist")
                attempts += 1
                continue

            if not matching_user.get("password"):
                print("Account data is corrupted.")
                attempts += 1
                continue

            if not verify_password(password, matching_user["password"]):
                print("Invalid password")
                attempts += 1
                continue

            saved_totp_secret = matching_user.get("totp_secret")
            if not saved_totp_secret:
                print("This profile does not have 2FA configured.")
                attempts += 1
                continue

            decrypted_secret = cipher.decrypt(saved_totp_secret.encode("utf-8")).decode("utf-8")
            totp = pyotp.TOTP(decrypted_secret)

            deleted = False
            for delete_attempt in range(3):
                print(f"\n--- DELETE ACCOUNT VERIFICATION (Attempts left: {3 - delete_attempt}) ---")
                user_code = input("Enter the 6-digit code from your authenticator app: ").strip()

                if totp.verify(user_code, valid_window=1):
                    delete_user(username)
                    print("Account was successfully deleted")
                    deleted = True
                    attempts = 0
                    break
                else:
                    print("Incorrect 2FA code. Please verify and try again.")

            if not deleted:
                attempts += 1

        elif choice == "4":
            print("Thanks for using the program")
            return False
        else:
            print("Invalid choice, please try again")

    print("\nToo many incorrect attempts. Program locked.")
    return False
