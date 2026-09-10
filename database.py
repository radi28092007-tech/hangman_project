import json
import os
import secrets

import keyring
from sqlcipher3 import dbapi2 as sqlite3


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(BASE_DIR, "hangman.db")
PASSWORDS_FILE = os.path.join(BASE_DIR, "passwords.json")
SCORES_FILE = os.path.join(BASE_DIR, "scores.json")

KEYRING_SERVICE = "HangmanGame"
KEYRING_DB_KEY_USERNAME = "sqlcipher-db-key"


def get_db_key():
    stored_key = keyring.get_password(KEYRING_SERVICE, KEYRING_DB_KEY_USERNAME)
    if stored_key is not None:
        return stored_key

    new_key = secrets.token_hex(32)  # 256-bit key, hex-encoded
    keyring.set_password(KEYRING_SERVICE, KEYRING_DB_KEY_USERNAME, new_key)
    return new_key


def get_connection():
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row

    # Must run before any other statement on this connection.
    connection.execute(f"PRAGMA key = \"x'{get_db_key()}'\"")

    # Cheap sanity check that the key is correct / db is readable.
    # If the key is wrong, this raises sqlite3.DatabaseError.
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
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS guessed_words (
                username TEXT NOT NULL,
                word TEXT NOT NULL,
                PRIMARY KEY (username, word),
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            );
            """
        )
        migrate_legacy_json(connection)


def migrate_legacy_json(connection):
    user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0 and os.path.exists(PASSWORDS_FILE):
        try:
            with open(PASSWORDS_FILE, "r", encoding="utf-8") as file:
                users = json.load(file)
        except (OSError, json.JSONDecodeError):
            users = []

        if isinstance(users, list):
            for user in users:
                if not isinstance(user, dict):
                    continue
                username = user.get("username")
                password_hash = user.get("password")
                totp_secret = user.get("totp_secret")
                if not all(isinstance(value, str) and value for value in (username, password_hash, totp_secret)):
                    continue
                connection.execute(
                    "INSERT OR IGNORE INTO users (username, password_hash, totp_secret) VALUES (?, ?, ?)",
                    (username, password_hash, totp_secret),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO scores (username)
                    SELECT username FROM users WHERE username = ?
                    """,
                    (username,),
                )

    score_count = connection.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    if score_count == 0 and os.path.exists(SCORES_FILE):
        try:
            with open(SCORES_FILE, "r", encoding="utf-8") as file:
                scores = json.load(file)
        except (OSError, json.JSONDecodeError):
            scores = {}

        if isinstance(scores, dict):
            for username, data in scores.items():
                if not isinstance(data, dict):
                    data = {"score": data}
                connection.execute(
                    """
                    INSERT OR IGNORE INTO scores (username)
                    SELECT username FROM users WHERE username = ?
                    """,
                    (username,),
                )
                connection.execute(
                    """
                    UPDATE scores
                    SET score = ?, wins = ?, losses = ?, total_games = ?
                    WHERE username = ?
                    """,
                    (
                        data.get("score", 0),
                        data.get("wins", 0),
                        data.get("losses", 0),
                        data.get("total_games", data.get("wins", 0) + data.get("losses", 0)),
                        username,
                    ),
                )
                for word in data.get("guessed_words", []):
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO guessed_words (username, word)
                        SELECT username, ? FROM users WHERE username = ?
                        """,
                        (word, username),
                    )


def load_data():
    initialize_database()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT username, password_hash, totp_secret FROM users ORDER BY username"
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
                INSERT INTO users (username, password_hash, totp_secret)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    totp_secret = excluded.totp_secret
                """,
                (user["username"], user["password"], user["totp_secret"]),
            )
            connection.execute("INSERT OR IGNORE INTO scores (username) VALUES (?)", (user["username"],))


def delete_user(username):
    initialize_database()
    with get_connection() as connection:
        connection.execute("DELETE FROM users WHERE username = ?", (username,))


def load_scores():
    initialize_database()
    with get_connection() as connection:
        score_rows = connection.execute(
            "SELECT username, score, wins, losses, total_games FROM scores"
        ).fetchall()
        word_rows = connection.execute(
            "SELECT username, word FROM guessed_words ORDER BY username, word"
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
        scores.setdefault(row["username"], {"score": 0, "wins": 0, "losses": 0, "total_games": 0, "guessed_words": []})
        scores[row["username"]]["guessed_words"].append(row["word"])
    return scores


def save_score(username, points, answer):
    initialize_database()
    with get_connection() as connection:
        connection.execute("INSERT OR IGNORE INTO scores (username) VALUES (?)", (username,))
        connection.execute(
            """
            UPDATE scores
            SET score = score + ?,
                wins = wins + ?,
                losses = losses + ?,
                total_games = total_games + 1
            WHERE username = ?
            """,
            (points, int(points > 0), int(points == 0), username),
        )
        if points > 0:
            connection.execute(
                "INSERT OR IGNORE INTO guessed_words (username, word) VALUES (?, ?)",
                (username, answer),
            )
