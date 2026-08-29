import sqlite3
from pathlib import Path


def ensure_database(path: Path) -> None:
    """Create the SQLite file and parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("SELECT 1;")
    finally:
        connection.close()


def database_is_ready(path: Path) -> bool:
    try:
        ensure_database(path)
    except OSError:
        return False
    return True
