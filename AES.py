import os
import json
import hashlib
import secrets
from cryptography.fernet import Fernet
from getpass import getpass
import pyotp  

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


def secure_hash_password(password, salt_hex=None):
    if salt_hex is None:
        salt_bytes = secrets.token_bytes(16) 
    else:
        salt_bytes = bytes.fromhex(salt_hex)

    combined_credential = password + SECRET_PEPPER
    password_bytes = combined_credential.encode("utf-8")

    hashed_bytes = hashlib.pbkdf2_hmac("sha256", password_bytes, salt_bytes, iterations=600000)
    return salt_bytes.hex(), hashed_bytes.hex()

def is_strong_password(password):
    special_chars = "!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~"
    return (len(password) >= 8 and 
            any(char.isdigit() for char in password) and 
            any(char.isalpha() for char in password) and 
            any(char.isupper() for char in password) and 
            any(char in special_chars for char in password))

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
    cipher = Fernet(secret_key)  # Initialize cipher globally for convenience
    
    while attempts < 3:
        print(f"\n--- AUTHENTICATION (Attempts left: {3 - attempts}) ---")
        print("0 - Forgotten Password")
        print("1 - Register")
        print("2 - Login")
        print("3 - Delete Account")
        print("4 - Exit")
        choice = input("Enter your choice (0-4): ").strip()

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

                    new_salt, new_hash = secure_hash_password(new_password)
                    user_record["salt"] = new_salt
                    user_record["password"] = new_hash

                    with open(pass_path, "w") as file:
                        json.dump(data, file, indent=4)

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
                
            salt_hex, hashed_hex = secure_hash_password(password)

            totp_secret = pyotp.random_base32()

            print("\n" + "="*50)
            print("SET UP TWO-FACTOR AUTHENTICATION")
            print(f"1. Open your authenticator app (e.g., Google Authenticator).")
            print(f"2. Add a new account manually using this secret key:")
            print(f"    {totp_secret}  ")
            input("Press Enter once you have saved/entered this key into your app...")

            encrypted_totp = cipher.encrypt(totp_secret.encode("utf-8")).decode("utf-8")

            new_entry = {
                "username": username,
                "salt": salt_hex,
                "password": hashed_hex,
                "totp_secret": encrypted_totp  
            }

            data.append(new_entry)

            with open(pass_path, "w") as file:
                json.dump(data, file, indent=4)
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
                    user_salt = user["salt"]
                    saved_totp_secret = user.get("totp_secret") 
                    
                    _, hashed_attempt = secure_hash_password(password, salt_hex=user_salt)

                    if secrets.compare_digest(hashed_attempt, user["password"]):
                        password_correct = True
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

            user_salt = matching_user.get("salt")
            if not user_salt:
                print("Account data is corrupted.")
                attempts += 1
                continue

            _, hashed_attempt = secure_hash_password(password, salt_hex=user_salt)
            if not secrets.compare_digest(hashed_attempt, matching_user.get("password", "")):
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
                    data = [user for user in data if user.get("username") != username]
                    with open(pass_path, "w") as file:
                        json.dump(data, file, indent=4)
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
