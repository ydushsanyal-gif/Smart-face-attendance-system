import os
from pathlib import Path
from datetime import date, datetime, time

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

USE_MYSQL = all([MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE])

if USE_MYSQL:
    DATABASE_URL = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    )
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    DATABASE_URL = f"sqlite:///{(BASE_DIR / 'face_attendance.db').as_posix()}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(bind=engine)


def initialize_database():
    with engine.begin() as conn:
        if not USE_MYSQL:
            conn.execute(text("PRAGMA foreign_keys = ON"))

        if USE_MYSQL:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        roll_no VARCHAR(50) UNIQUE NOT NULL,
                        email VARCHAR(100) NOT NULL,
                        phone VARCHAR(20) NOT NULL,
                        face_id VARCHAR(255) UNIQUE,
                        image_url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS attendance (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        date DATE NOT NULL,
                        time TIME NOT NULL,
                        status VARCHAR(20) DEFAULT 'Present',
                        confidence FLOAT,
                        image_url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, date),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS unknown_faces (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        image_url TEXT NOT NULL,
                        captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            return

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    roll_no TEXT UNIQUE NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    face_id TEXT UNIQUE,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    status TEXT DEFAULT 'Present',
                    confidence REAL,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, date),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS unknown_faces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_url TEXT NOT NULL,
                    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def db_execute(query, params=None, fetchone=False, fetchall=False, commit=False):
    params = params or {}
    if not USE_MYSQL:
        params = {
            key: (
                value.isoformat()
                if isinstance(value, (date, datetime, time))
                else value
            )
            for key, value in params.items()
        }
    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        if commit:
            conn.commit()
        if fetchone:
            row = result.mappings().fetchone()
            return dict(row) if row else None
        if fetchall:
            return [dict(row) for row in result.mappings().fetchall()]
        return result


initialize_database()
