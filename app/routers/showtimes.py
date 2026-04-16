"""
Showtime routes: list upcoming showtimes, showtime detail with seat availability.
"""
from datetime import datetime, date, time
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.db.connection import get_db

router = APIRouter()

# Seat layout: rows A–J, seats 1–10
ROWS = list("ABCDEFGHIJ")
SEATS_PER_ROW = 10


def _all_seat_labels() -> list[str]:
    return [f"{row}{num}" for row in ROWS for num in range(1, SEATS_PER_ROW + 1)]


def _compute_dynamic_price(base_price: float, occupancy: int, capacity: int,
                             show_date: date, show_time: time) -> dict:
    """Apply dynamic pricing rules and return price + reason."""
    if capacity == 0:
        return {"final_price": base_price, "price_modifier": "standard", "modifier_pct": 0}

    fill_pct = occupancy / capacity * 100
    now = datetime.now()
    showtime_dt = datetime.combine(show_date, show_time)
    hours_until = (showtime_dt - now).total_seconds() / 3600

    if fill_pct < 20 and 0 < hours_until < 2:
        return {
            "final_price": round(base_price * 0.85, 2),
            "price_modifier": "last_minute_discount",
            "modifier_pct": -15,
        }
    elif fill_pct > 80:
        return {
            "final_price": round(base_price * 1.15, 2),
            "price_modifier": "high_demand_surcharge",
            "modifier_pct": 15,
        }
    else:
        return {"final_price": base_price, "price_modifier": "standard", "modifier_pct": 0}


@router.get("")
def list_showtimes(
    genre: Optional[str] = Query(default=None),
    date_filter: Optional[str] = Query(default=None, alias="date"),
):
    with get_db() as cur:
        query = """
            SELECT s.ShowtimeID, s.MovieID, s.Date, s.StartTime, s.BasePrice,
                   s.CurrentOccupancy, t.TotalCapacity,
                   m.Title, m.Genre, m.Duration, m.PosterURL,
                   t.Name AS TheaterName, t.ScreenType,
                   em.TMDB_Rating, em.TrendingStatus
            FROM Showtimes s
            JOIN Movies m ON s.MovieID = m.MovieID
            JOIN Theaters t ON s.TheaterID = t.TheaterID
            LEFT JOIN External_Metadata em ON m.MovieID = em.MovieID
            WHERE (s.Date > CURRENT_DATE OR (s.Date = CURRENT_DATE AND s.StartTime > CURRENT_TIME))
        """
        params = []
        if genre:
            query += " AND m.Genre ILIKE %s"
            params.append(f"%{genre}%")
        if date_filter:
            query += " AND s.Date = %s"
            params.append(date_filter)
        query += " ORDER BY s.Date, s.StartTime LIMIT 50"

        cur.execute(query, params)
        rows = cur.fetchall()

    result = []
    for r in rows:
        pricing = _compute_dynamic_price(
            float(r["baseprice"]), r["currentoccupancy"],
            r["totalcapacity"], r["date"], r["starttime"]
        )
        result.append({
            "showtime_id": r["showtimeid"],
            "movie_id": r["movieid"],
            "title": r["title"],
            "genre": r["genre"],
            "duration": r["duration"],
            "poster_url": r["posterurl"],
            "date": str(r["date"]),
            "start_time": str(r["starttime"]),
            "base_price": float(r["baseprice"]),
            "current_occupancy": r["currentoccupancy"],
            "total_capacity": r["totalcapacity"],
            "fill_pct": round(r["currentoccupancy"] / r["totalcapacity"] * 100, 1) if r["totalcapacity"] else 0,
            "theater_name": r["theatername"],
            "screen_type": r["screentype"],
            "tmdb_rating": float(r["tmdb_rating"]) if r["tmdb_rating"] else None,
            "trending_status": r["trendingstatus"],
            **pricing,
        })
    return result


@router.get("/{showtime_id}")
def get_showtime(showtime_id: int):
    with get_db() as cur:
        cur.execute(
            """
            SELECT s.ShowtimeID, s.MovieID, s.Date, s.StartTime, s.BasePrice,
                   s.CurrentOccupancy, t.TotalCapacity, t.TheaterID,
                   m.Title, m.Genre, m.Duration, m.PosterURL, m.Description,
                   t.Name AS TheaterName, t.ScreenType,
                   em.TMDB_Rating, em.TMDB_Popularity, em.TrendingStatus
            FROM Showtimes s
            JOIN Movies m ON s.MovieID = m.MovieID
            JOIN Theaters t ON s.TheaterID = t.TheaterID
            LEFT JOIN External_Metadata em ON m.MovieID = em.MovieID
            WHERE s.ShowtimeID = %s
            """,
            (showtime_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Showtime not found")

    pricing = _compute_dynamic_price(
        float(row["baseprice"]), row["currentoccupancy"],
        row["totalcapacity"], row["date"], row["starttime"]
    )
    return {
        "showtime_id": row["showtimeid"],
        "movie_id": row["movieid"],
        "theater_id": row["theaterid"],
        "title": row["title"],
        "genre": row["genre"],
        "duration": row["duration"],
        "description": row["description"],
        "poster_url": row["posterurl"],
        "date": str(row["date"]),
        "start_time": str(row["starttime"]),
        "base_price": float(row["baseprice"]),
        "current_occupancy": row["currentoccupancy"],
        "total_capacity": row["totalcapacity"],
        "fill_pct": round(row["currentoccupancy"] / row["totalcapacity"] * 100, 1) if row["totalcapacity"] else 0,
        "theater_name": row["theatername"],
        "screen_type": row["screentype"],
        "tmdb_rating": float(row["tmdb_rating"]) if row["tmdb_rating"] else None,
        "tmdb_popularity": float(row["tmdb_popularity"]) if row["tmdb_popularity"] else None,
        "trending_status": row["trendingstatus"],
        **pricing,
    }


@router.get("/{showtime_id}/seats")
def get_seats(showtime_id: int):
    """Return all seat labels with their booked/available status."""
    with get_db() as cur:
        cur.execute(
            """
            SELECT s.TotalCapacity, st.CurrentOccupancy, st.BasePrice,
                   st.Date, st.StartTime
            FROM Showtimes st
            JOIN Theaters s ON st.TheaterID = s.TheaterID
            WHERE st.ShowtimeID = %s
            """,
            (showtime_id,),
        )
        info = cur.fetchone()
        if not info:
            raise HTTPException(status_code=404, detail="Showtime not found")

        cur.execute(
            "SELECT SeatNumber FROM Bookings WHERE ShowtimeID = %s AND Status = 'confirmed'",
            (showtime_id,),
        )
        booked = {r["seatnumber"] for r in cur.fetchall()}

    pricing = _compute_dynamic_price(
        float(info["baseprice"]), info["currentoccupancy"],
        info["totalcapacity"], info["date"], info["starttime"]
    )

    all_seats = _all_seat_labels()
    seats = [
        {"seat": s, "status": "taken" if s in booked else "available"}
        for s in all_seats
    ]
    return {
        "seats": seats,
        "booked_count": len(booked),
        "total_seats": len(all_seats),
        **pricing,
    }
