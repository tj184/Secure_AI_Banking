
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "securebank-development-secret-change-this",
    )

    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"

    # Database configuration
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'securebank.db'}",
    )

    # Ollama configuration
    OLLAMA_BASE_URL = os.environ.get(
        "OLLAMA_BASE_URL",
        "http://localhost:11434",
    )

    OLLAMA_MODEL = os.environ.get(
        "OLLAMA_MODEL",
        "gemma4:e2b",
    )

    # Session configuration
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    )

    PERMANENT_SESSION_LIFETIME = 1800

    # Manager authentication
    MANAGER_USERNAME = os.environ.get(
        "MANAGER_USERNAME",
        "admin",
    )

    MANAGER_PASSWORD_HASH = os.environ.get(
        "MANAGER_PASSWORD_HASH",
        "",
    )

    # Request limits
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024

    JSON_SORT_KEYS = False
