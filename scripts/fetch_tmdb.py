"""
fetch_tmdb.py — Milestone 1, Step 3

Fetches live metadata from the TMDB API for every Movie row that has a TMDB_ID
and upserts the results into the External_Metadata table.

Designed to be run:
  - Once during Milestone 1 setup:  python scripts/fetch_tmdb.py
  - As a periodic cron job (Milestone 2+) to keep metadata fresh.

Requirements:
  - TMDB_API_KEY must be set in .env
  - Movies table must already be populated (run seed_db.py first)
"""

import logging
import os
import sys
import time
from datetime import datetime, timezone

import psycopg2
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# TMDB rate limit: ~40 requests / 10 seconds on the free tier.
# A small sleep keeps us well within limits.
REQUEST_DELAY_SECONDS = 0.3

# Popularity thresholds for TrendingStatus classification
TRENDING_THRESHOLD = 100.0
DECLINING_THRESHOLD = 20.0


def classify_trending(popularity: float) -> str:
    if popularity >= TRENDING_THRESHOLD:
        return "trending"
    if popularity <= DECLINING_THRESHOLD:
        return "declining"
    return "normal"


def fetch_movie_details(tmdb_id: int) -> dict | None:
    """Call TMDB /movie/{id} and return the relevant fields, or None on error."""
    url = f"{settings.TMDB_BASE_URL}/movie/{tmdb_id}"
    params = {"api_key": settings.TMDB_API_KEY, "language": "en-US"}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "popularity": data.get("popularity"),
            "vote_average": data.get("vote_average"),
        }
    except requests.exceptions.HTTPError as e:
        logger.warning("HTTP error for TMDB ID %d: %s", tmdb_id, e)
    except requests.exceptions.RequestException as e:
        logger.error("Network error for TMDB ID %d: %s", tmdb_id, e)

    return None


def get_movies_with_tmdb_ids(conn: psycopg2.extensions.connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT MovieID, Title, TMDB_ID FROM Movies WHERE TMDB_ID IS NOT NULL"
        )
        rows = cur.fetchall()
    return [{"movie_id": r[0], "title": r[1], "tmdb_id": r[2]} for r in rows]


def upsert_metadata(
    conn: psycopg2.extensions.connection,
    movie_id: int,
    popularity: float,
    rating: float,
    trending_status: str,
) -> None:
    """Insert or update the External_Metadata row for a given movie."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO External_Metadata
                (MovieID, TMDB_Popularity, TMDB_Rating, TrendingStatus, LastUpdated)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (MovieID) DO UPDATE
                SET TMDB_Popularity = EXCLUDED.TMDB_Popularity,
                    TMDB_Rating     = EXCLUDED.TMDB_Rating,
                    TrendingStatus  = EXCLUDED.TrendingStatus,
                    LastUpdated     = EXCLUDED.LastUpdated
            """,
            (movie_id, popularity, rating, trending_status,
             datetime.now(timezone.utc)),
        )
    conn.commit()


def main() -> None:
    logger.info("=== CineBook — TMDB Metadata Fetch ===")

    if not settings.TMDB_API_KEY:
        logger.error(
            "TMDB_API_KEY is not set. Add it to your .env file and retry."
        )
        sys.exit(1)

    conn = psycopg2.connect(settings.db_dsn)
    try:
        movies = get_movies_with_tmdb_ids(conn)
        logger.info("Found %d movies with TMDB IDs.", len(movies))

        success, skipped = 0, 0
        for movie in movies:
            logger.info("Fetching: %s (TMDB ID: %d)", movie["title"], movie["tmdb_id"])
            details = fetch_movie_details(movie["tmdb_id"])

            if details is None:
                logger.warning("  Skipping '%s' — no data returned.", movie["title"])
                skipped += 1
                continue

            popularity = details["popularity"] or 0.0
            rating = details["vote_average"] or 0.0
            trending_status = classify_trending(popularity)

            upsert_metadata(
                conn,
                movie_id=movie["movie_id"],
                popularity=popularity,
                rating=rating,
                trending_status=trending_status,
            )
            logger.info(
                "  Updated — popularity: %.1f, rating: %.1f, status: %s",
                popularity, rating, trending_status,
            )
            success += 1
            time.sleep(REQUEST_DELAY_SECONDS)

        logger.info(
            "=== Fetch complete. Success: %d | Skipped: %d ===", success, skipped
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
