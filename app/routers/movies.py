<<<<<<< HEAD
"""
Movie catalog routes.
"""
from fastapi import APIRouter, Query
from typing import Optional
=======
from fastapi import APIRouter
>>>>>>> ef8d6d0562c39a4fe5763bcdc0238f89f32e0f48
from app.db.connection import get_db

router = APIRouter()


<<<<<<< HEAD
@router.get("")
def list_movies(genre: Optional[str] = Query(default=None)):
    with get_db() as cur:
        if genre:
            cur.execute(
                """
                SELECT m.MovieID, m.Title, m.Genre, m.Duration, m.ReleaseDate,
                       m.Description, m.PosterURL,
                       em.TMDB_Rating, em.TMDB_Popularity, em.TrendingStatus
                FROM Movies m
                LEFT JOIN External_Metadata em ON m.MovieID = em.MovieID
                WHERE m.Genre ILIKE %s
                ORDER BY em.TMDB_Popularity DESC NULLS LAST
                """,
                (f"%{genre}%",),
            )
        else:
            cur.execute(
                """
                SELECT m.MovieID, m.Title, m.Genre, m.Duration, m.ReleaseDate,
                       m.Description, m.PosterURL,
                       em.TMDB_Rating, em.TMDB_Popularity, em.TrendingStatus
                FROM Movies m
                LEFT JOIN External_Metadata em ON m.MovieID = em.MovieID
                ORDER BY em.TMDB_Popularity DESC NULLS LAST
                """
            )
        rows = cur.fetchall()

    return [
        {
            "movie_id": r["movieid"],
            "title": r["title"],
            "genre": r["genre"],
            "duration": r["duration"],
            "release_date": str(r["releasedate"]) if r["releasedate"] else None,
            "description": r["description"],
            "poster_url": r["posterurl"],
            "tmdb_rating": float(r["tmdb_rating"]) if r["tmdb_rating"] else None,
            "tmdb_popularity": float(r["tmdb_popularity"]) if r["tmdb_popularity"] else None,
            "trending_status": r["trendingstatus"],
        }
        for r in rows
    ]
=======
@router.get("/")
def get_movies():
    with get_db() as cur:
        cur.execute("""
            SELECT m.*, em.tmdb_rating, em.tmdb_popularity, em.trendingstatus
            FROM Movies m
            LEFT JOIN External_Metadata em ON m.MovieID = em.MovieID
        """)
        return cur.fetchall()
>>>>>>> ef8d6d0562c39a4fe5763bcdc0238f89f32e0f48


@router.get("/{movie_id}")
def get_movie(movie_id: int):
    with get_db() as cur:
<<<<<<< HEAD
        cur.execute(
            """
            SELECT m.MovieID, m.Title, m.Genre, m.Duration, m.ReleaseDate,
                   m.Description, m.PosterURL,
                   em.TMDB_Rating, em.TMDB_Popularity, em.TrendingStatus
            FROM Movies m
            LEFT JOIN External_Metadata em ON m.MovieID = em.MovieID
            WHERE m.MovieID = %s
            """,
            (movie_id,),
        )
        row = cur.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Movie not found")
    return {
        "movie_id": row["movieid"],
        "title": row["title"],
        "genre": row["genre"],
        "duration": row["duration"],
        "release_date": str(row["releasedate"]) if row["releasedate"] else None,
        "description": row["description"],
        "poster_url": row["posterurl"],
        "tmdb_rating": float(row["tmdb_rating"]) if row["tmdb_rating"] else None,
        "tmdb_popularity": float(row["tmdb_popularity"]) if row["tmdb_popularity"] else None,
        "trending_status": row["trendingstatus"],
    }


@router.get("/{movie_id}/showtimes")
def movie_showtimes(movie_id: int):
    with get_db() as cur:
        cur.execute(
            """
            SELECT s.ShowtimeID, s.Date, s.StartTime, s.BasePrice,
                   s.CurrentOccupancy, t.TotalCapacity,
                   t.Name AS TheaterName, t.ScreenType
            FROM Showtimes s
            JOIN Theaters t ON s.TheaterID = t.TheaterID
            WHERE s.MovieID = %s
              AND (s.Date > CURRENT_DATE OR (s.Date = CURRENT_DATE AND s.StartTime > CURRENT_TIME))
            ORDER BY s.Date, s.StartTime
            """,
            (movie_id,),
        )
        rows = cur.fetchall()
    return [
        {
            "showtime_id": r["showtimeid"],
            "date": str(r["date"]),
            "start_time": str(r["starttime"]),
            "base_price": float(r["baseprice"]),
            "current_occupancy": r["currentoccupancy"],
            "total_capacity": r["totalcapacity"],
            "theater_name": r["theatername"],
            "screen_type": r["screentype"],
            "fill_pct": round(r["currentoccupancy"] / r["totalcapacity"] * 100, 1) if r["totalcapacity"] else 0,
        }
        for r in rows
    ]
=======
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
>>>>>>> ef8d6d0562c39a4fe5763bcdc0238f89f32e0f48
