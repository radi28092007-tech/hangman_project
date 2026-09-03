import os
import json
import hashlib
import secrets
from cryptography.fernet import Fernet
from getpass import getpass

KEY_FILE = "secret.key"
pass_path = r"passwords.json"

# Key management
if os.path.exists(KEY_FILE):
    with open(KEY_FILE, "rb") as file:
        secret_key = file.read()
else:
    secret_key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as file:
        file.write(secret_key)

# Using the AES key as a secret Pepper to strengthen hashes
SECRET_PEPPER = secret_key.decode("utf-8")



def secure_hash_password(password, salt_hex = None):

    if salt_hex is None:
        salt_bytes = secrets.token_bytes(16) 

    else:
        salt_bytes = bytes.fromhex(salt_hex)

    combined_credential = password + SECRET_PEPPER
    password_bytes = combined_credential.encode("utf-8")

    hashed_bytes = hashlib.pbkdf2_hmac("sha256", password_bytes, salt_bytes, iterations = 600000) # pdkdf2_hmac with SHA-256, 600,000 iterations, preventing brute-force attacks
    return salt_bytes.hex(), hashed_bytes.hex() # Return both salt and hash as hex strings



def load_data():
    if os.path.exists(pass_path):
        with open(pass_path, "r") as file:
            try:
                data = json.load(file)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
    return []


# Main logic
def authentication():
    attempts = 0  
    
    while attempts < 3:
        print(f"\n--- AUTHENTICATION (Attempts left: {3 - attempts}) ---")
        print("1 - Register")
        print("2 - Login")
        print("3 - Exit")
        choice = input("Enter your choice (1-3): ").strip()

        if choice == "1":
            username = input("Enter your username: ").strip()
            password = getpass(prompt = "Enter your password: ", echo_char = "*").strip()

            if not username or not password:
                print("Username / Password was left empty, please try again")
                continue

            data = load_data()
            user_exists = any(user["username"] == username for user in data)
            if user_exists:
                print("Username already exists, please try again")
                continue

            if len(password) < 8 or not any(char.isdigit() for char in password) or not any(char.isalpha() for char in password) or not any(char.isupper() for char in password) or not any(char in ("!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~") for char in password):
                print("At least 8 characters, at least one number, one uppercase letter, and special character")
                continue
                
          
            salt_hex, hashed_hex = secure_hash_password(password)

            new_entry = {
                "username": username,
                "salt": salt_hex,
                "password": hashed_hex}

            data.append(new_entry)

            with open(pass_path, "w") as file:
                json.dump(data, file, indent=4)
            print("Registration was successful")

        elif choice == "2":
            username = input("Enter your username: ").strip()
            password = getpass(prompt = "Enter your password: ", echo_char = "*").strip()

            data = load_data()
            user_found = False
            password_correct = False

            for user in data:
                if user["username"] == username:
                    user_found = True

                    user_salt = user["salt"]
                    _, hashed_attempt = secure_hash_password(password, salt_hex = user_salt)

                    if secrets.compare_digest(hashed_attempt, user["password"]): # prevents timing attacks
                        password_correct = True
                    break

            if user_found and password_correct:
                print(f"Login successful! Welcome, {username}.")
                return username  # Returns the username directly to Hangman
            else:
                print("Invalid password or username")
                attempts += 1  

        elif choice == "3":
            print("Thanks for using the program")
            return False
        else:
            print("Invalid choice, please try again")

    # Exit after 3 failed attempts
    print("\nToo many incorrect attempts. Program locked.")
    return False
