"""
init_db.py — Create and seed the SQLite database.

Run once before starting the server:
    python init_db.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "lab.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL,
    email    TEXT    UNIQUE NOT NULL,
    cohort   TEXT    NOT NULL,
    score    REAL    DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    UNIQUE NOT NULL,
    title       TEXT    NOT NULL,
    credits     INTEGER NOT NULL DEFAULT 3,
    instructor  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id),
    course_id  INTEGER NOT NULL REFERENCES courses(id),
    grade      REAL,
    status     TEXT    NOT NULL DEFAULT 'active',
    enrolled_at TEXT   NOT NULL DEFAULT (date('now'))
);
"""

SEED_SQL = """
INSERT OR IGNORE INTO students (name, email, cohort, score) VALUES
    ('Alice Nguyen',   'alice@example.com',   'A1', 92.5),
    ('Bob Tran',       'bob@example.com',     'A1', 78.0),
    ('Carol Le',       'carol@example.com',   'A2', 85.3),
    ('David Pham',     'david@example.com',   'A2', 61.0),
    ('Eva Hoang',      'eva@example.com',     'B1', 95.1),
    ('Frank Vo',       'frank@example.com',   'B1', 70.4),
    ('Grace Do',       'grace@example.com',   'B2', 88.9),
    ('Henry Bui',      'henry@example.com',   'B2', 55.0),
    ('Iris Dang',      'iris@example.com',    'A1', 99.0),
    ('Jack Ngo',       'jack@example.com',    'A2', 73.5);

INSERT OR IGNORE INTO courses (code, title, credits, instructor) VALUES
    ('CS101', 'Intro to Programming',   3, 'Dr. Smith'),
    ('CS201', 'Data Structures',        4, 'Dr. Jones'),
    ('CS301', 'Machine Learning',       3, 'Dr. Lee'),
    ('CS401', 'Distributed Systems',   4, 'Dr. Pham'),
    ('CS501', 'NLP & LLMs',            3, 'Dr. Nguyen');

INSERT OR IGNORE INTO enrollments (student_id, course_id, grade, status) VALUES
    (1, 1, 90.0, 'active'),
    (1, 2, 88.5, 'active'),
    (2, 1, 75.0, 'active'),
    (3, 3, 82.0, 'active'),
    (4, 2, 60.0, 'active'),
    (5, 3, 95.0, 'active'),
    (5, 5, 98.0, 'active'),
    (6, 1, 68.0, 'active'),
    (7, 4, 87.5, 'active'),
    (8, 2, 52.0, 'dropped'),
    (9, 5, 99.0, 'active'),
    (10, 3, 71.0, 'active');
"""


def create_database(db_path: Path = DB_PATH) -> Path:
    """Create the SQLite database, apply schema, and seed data.

    Returns the absolute path to the created database file.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()

    print(f"[init_db] Database ready at: {db_path.resolve()}")
    return db_path.resolve()


if __name__ == "__main__":
    create_database()
