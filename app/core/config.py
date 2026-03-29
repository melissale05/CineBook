"""
Central configuration for CineBook.

All environment variables are read here.  Other modules should import
from this file rather than calling os.getenv / dotenv directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # reads .env if present; safe to call even when vars are already set


class Settings:
    # --- Database ---
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "cinebook")
    DB_USER: str = os.getenv("DB_USER", "cinebook_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # --- TMDB ---
    TMDB_API_KEY: str = os.getenv("TMDB_API_KEY", "")
    TMDB_BASE_URL: str = os.getenv("TMDB_BASE_URL", "https://api.themoviedb.org/3")

    @property
    def db_dsn(self) -> str:
        """psycopg2 connection string."""
        return (
            f"host={self.DB_HOST} "
            f"port={self.DB_PORT} "
            f"dbname={self.DB_NAME} "
            f"user={self.DB_USER} "
            f"password={self.DB_PASSWORD}"
        )


settings = Settings()
