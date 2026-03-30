from fastapi import APIRouter
from app.db.connection import get_db

router = APIRouter()


@router.get("/")
def get_movies():
    with get_db() as cur:
        cur.execute("""
            SELECT m.*, em.tmdb_rating, em.tmdb_popularity, em.trendingstatus
            FROM Movies m
            LEFT JOIN External_Metadata em ON m.MovieID = em.MovieID
        """)
        return cur.fetchall()


@router.get("/{movie_id}")
def get_movie(movie_id: int):
    with get_db() as cur:
        cur.execute("""
            SELECT * FROM Movies WHERE MovieID = %s
        """, (movie_id,))
        return cur.fetchone()


@router.get("/showtimes/{movie_id}")
def get_showtimes(movie_id: int):
    with get_db() as cur:
        cur.execute("""
            SELECT * FROM Showtimes WHERE MovieID = %s
        """, (movie_id,))
        return cur.fetchall()
