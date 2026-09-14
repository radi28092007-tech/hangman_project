import os
import secrets
import sys
import keyring
from sqlcipher3 import dbapi2 as sqlite3


def get_application_directory():

    if getattr(sys, "frozen", False):
        # PyInstaller executable
        return os.path.dirname(os.path.abspath(sys.executable))

    # Normal Python execution
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_application_directory()

# All data belonging to this particular executable installation
DATA_DIR = os.path.join(BASE_DIR, "Hangman_Game_Data")

os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_FILE = os.path.join(DATA_DIR, "hangman.db")
KEYRING_SERVICE = "HangmanGame"

def get_keyring_username():
    normalized_path = os.path.normcase(os.path.abspath(BASE_DIR))

    import hashlib

    path_hash = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()[:32]
    return f"sqlcipher-db-key-{path_hash}"


KEYRING_DB_KEY_USERNAME = get_keyring_username()


def get_db_key():

    stored_key = keyring.get_password(KEYRING_SERVICE, KEYRING_DB_KEY_USERNAME)
    if stored_key is not None:
        return stored_key

    new_key = secrets.token_hex(32)

    keyring.set_password(KEYRING_SERVICE, KEYRING_DB_KEY_USERNAME, new_key)
    return new_key



def get_connection():

    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    db_key = get_db_key()


    connection.execute(f'PRAGMA key = "x\'{db_key}\'"')
    connection.execute("SELECT count(*) FROM sqlite_master")
    connection.execute("PRAGMA foreign_keys = ON")

    return connection



def initialize_database():

    with get_connection() as connection:

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                totp_secret TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scores (
                username TEXT PRIMARY KEY,
                score INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                total_games INTEGER NOT NULL DEFAULT 0,

                FOREIGN KEY (username)
                    REFERENCES users(username)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS guessed_words (
                username TEXT NOT NULL,
                word TEXT NOT NULL,

                PRIMARY KEY (username, word),

                FOREIGN KEY (username)
                    REFERENCES users(username)
                    ON DELETE CASCADE
            );
            """
        )



def load_data():
    initialize_database()

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                username,
                password_hash,
                totp_secret
            FROM users
            ORDER BY username
            """
        ).fetchall()

    return [
        {
            "username": row["username"],
            "password": row["password_hash"],
            "totp_secret": row["totp_secret"],
        }
        for row in rows
    ]


def save_data(users):
    initialize_database()

    with get_connection() as connection:

        for user in users:

            connection.execute(
                """
                INSERT INTO users
                (
                    username,
                    password_hash,
                    totp_secret
                )
                VALUES (?, ?, ?)

                ON CONFLICT(username)
                DO UPDATE SET

                    password_hash =
                        excluded.password_hash,

                    totp_secret =
                        excluded.totp_secret
                """,
                (
                    user["username"],
                    user["password"],
                    user["totp_secret"]
                )
            )

            connection.execute(
                """
                INSERT OR IGNORE INTO scores
                (username)
                VALUES (?)
                """,
                (user["username"],)
            )


def delete_user(username):
    initialize_database()

    with get_connection() as connection:

        connection.execute(
            "DELETE FROM users WHERE username = ?",
            (username,)
        )


def load_scores():
    initialize_database()

    with get_connection() as connection:

        score_rows = connection.execute(
            """
            SELECT
                username,
                score,
                wins,
                losses,
                total_games
            FROM scores
            """
        ).fetchall()

        word_rows = connection.execute(
            """
            SELECT
                username,
                word
            FROM guessed_words
            ORDER BY username, word
            """
        ).fetchall()

    scores = {
        row["username"]: {
            "score": row["score"],
            "wins": row["wins"],
            "losses": row["losses"],
            "total_games": row["total_games"],
            "guessed_words": [],
        }
        for row in score_rows
    }

    for row in word_rows:

        scores.setdefault(
            row["username"],
            {
                "score": 0,
                "wins": 0,
                "losses": 0,
                "total_games": 0,
                "guessed_words": [],
            }
        )

        scores[row["username"]]["guessed_words"].append(row["word"])

    return scores

def save_score(username, points, answer):
    initialize_database()

    with get_connection() as connection:

        connection.execute(
            """
            INSERT OR IGNORE INTO scores
            (username)
            VALUES (?)
            """,
            (username,)
        )

        connection.execute(
            """
            UPDATE scores

            SET
                score = score + ?,
                wins = wins + ?,
                losses = losses + ?,
                total_games = total_games + 1

            WHERE username = ?
            """,
            (
                points,
                int(points > 0),
                int(points == 0),
                username
            )
        )

        if points > 0:

            connection.execute(
                """
                INSERT OR IGNORE INTO guessed_words
                (
                    username,
                    word
                )
                VALUES (?, ?)
                """,
                (
                    username,
                    answer
                )
            )
