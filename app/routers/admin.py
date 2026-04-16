"""
Admin-only routes: forecasting dashboard, alerts, inventory management.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.db.connection import get_db
from app.dependencies import get_current_user, require_admin

router = APIRouter()


def _admin_check(current_user: dict = Depends(get_current_user)) -> dict:
    return require_admin(current_user)


# ── Dashboard / Forecasts ─────────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(current_user: dict = Depends(_admin_check)):
    """Return the materialized forecast dashboard view (refresh first)."""
    with get_db() as cur:
        # Refresh materialized view with latest data
        try:
            cur.execute("REFRESH MATERIALIZED VIEW mv_forecast_dashboard")
        except Exception:
            pass  # view may have no data yet; we still return what we can

        cur.execute(
            """
            SELECT ForecastID, ShowtimeID, MovieTitle, Genre,
                   ShowDate, StartTime, TheaterName,
                   BasePrice, TotalCapacity, CurrentOccupancy, CurrentFillPct,
                   PredictedOccupancy, PredictedRevenue, RecommendationLevel,
                   TMDB_Rating, TrendingStatus, RevenueRankOnDate, CumulativePredictedRevenue
            FROM mv_forecast_dashboard
            ORDER BY ShowDate, StartTime
            LIMIT 50
            """
        )
        rows = cur.fetchall()

    return [
        {
            "forecast_id": r["forecastid"],
            "showtime_id": r["showtimeid"],
            "movie_title": r["movietitle"],
            "genre": r["genre"],
            "show_date": str(r["showdate"]),
            "start_time": str(r["starttime"]),
            "theater_name": r["theatername"],
            "base_price": float(r["baseprice"]),
            "total_capacity": r["totalcapacity"],
            "current_occupancy": r["currentoccupancy"],
            "current_fill_pct": float(r["currentfillpct"]) if r["currentfillpct"] else 0,
            "predicted_occupancy": float(r["predictedoccupancy"]) if r["predictedoccupancy"] else None,
            "predicted_revenue": float(r["predictedrevenue"]) if r["predictedrevenue"] else None,
            "recommendation_level": r["recommendationlevel"],
            "tmdb_rating": float(r["tmdb_rating"]) if r["tmdb_rating"] else None,
            "trending_status": r["trendingstatus"],
            "revenue_rank_on_date": r.get("revenuerankondatee") or r.get("revenuerankondatee"),
            "cumulative_predicted_revenue": float(r["cumulativepredictedrevenue"]) if r["cumulativepredictedrevenue"] else None,
        }
        for r in rows
    ]


@router.post("/forecasts/run")
def run_forecasting(current_user: dict = Depends(_admin_check)):
    """Run the demand forecasting stored procedure."""
    admin_id = current_user["user_id"]
    with get_db() as cur:
        cur.execute("CALL run_demand_forecasting(%s)", (admin_id,))
    return {"message": "Forecasting complete"}


@router.get("/forecasts")
def get_forecasts(current_user: dict = Depends(_admin_check)):
    """Return raw Demand_Forecasts rows with showtime info."""
    with get_db() as cur:
        cur.execute(
            """
            SELECT df.ForecastID, df.ShowtimeID, df.PredictedOccupancy,
                   df.PredictedRevenue, df.RecommendationLevel, df.GeneratedAt,
                   m.Title, s.Date, s.StartTime, s.BasePrice,
                   s.CurrentOccupancy, t.TotalCapacity,
                   t.Name AS TheaterName,
                   em.TrendingStatus
            FROM Demand_Forecasts df
            JOIN Showtimes s ON df.ShowtimeID = s.ShowtimeID
            JOIN Movies m ON s.MovieID = m.MovieID
            JOIN Theaters t ON s.TheaterID = t.TheaterID
            LEFT JOIN External_Metadata em ON m.MovieID = em.MovieID
            ORDER BY df.GeneratedAt DESC
            LIMIT 50
            """
        )
        rows = cur.fetchall()

    return [
        {
            "forecast_id": r["forecastid"],
            "showtime_id": r["showtimeid"],
            "title": r["title"],
            "date": str(r["date"]),
            "start_time": str(r["starttime"]),
            "base_price": float(r["baseprice"]),
            "theater_name": r["theatername"],
            "current_occupancy": r["currentoccupancy"],
            "total_capacity": r["totalcapacity"],
            "fill_pct": round(r["currentoccupancy"] / r["totalcapacity"] * 100, 1) if r["totalcapacity"] else 0,
            "predicted_occupancy": float(r["predictedoccupancy"]) if r["predictedoccupancy"] else None,
            "predicted_revenue": float(r["predictedrevenue"]) if r["predictedrevenue"] else None,
            "recommendation_level": r["recommendationlevel"],
            "trending_status": r["trendingstatus"],
            "generated_at": r["generatedat"].isoformat() if r["generatedat"] else None,
        }
        for r in rows
    ]


@router.get("/alerts")
def get_alerts(current_user: dict = Depends(_admin_check)):
    with get_db() as cur:
        cur.execute(
            """
            SELECT a.AlertID, a.ShowtimeID, a.AlertType, a.Message, a.CreatedAt, a.Resolved,
                   m.Title, s.Date, s.StartTime
            FROM Admin_Alerts a
            JOIN Showtimes s ON a.ShowtimeID = s.ShowtimeID
            JOIN Movies m ON s.MovieID = m.MovieID
            ORDER BY a.CreatedAt DESC
            LIMIT 30
            """
        )
        rows = cur.fetchall()

    return [
        {
            "alert_id": r["alertid"],
            "showtime_id": r["showtimeid"],
            "alert_type": r["alerttype"],
            "message": r["message"],
            "created_at": r["createdat"].isoformat() if r["createdat"] else None,
            "resolved": r["resolved"],
            "title": r["title"],
            "date": str(r["date"]),
            "start_time": str(r["starttime"]),
        }
        for r in rows
    ]


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, current_user: dict = Depends(_admin_check)):
    with get_db() as cur:
        cur.execute(
            "UPDATE Admin_Alerts SET Resolved = TRUE WHERE AlertID = %s RETURNING AlertID",
            (alert_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert resolved", "alert_id": alert_id}


# ── User Management ───────────────────────────────────────────────────────────

@router.get("/users")
def get_users(current_user: dict = Depends(_admin_check)):
    with get_db() as cur:
        cur.execute(
            """
            SELECT UserID, Name, Email, Role, FavoriteGenre, LoyaltyPoints, CreatedAt
            FROM Users ORDER BY CreatedAt DESC
            """
        )
        rows = cur.fetchall()
    return [
        {
            "user_id": r["userid"],
            "name": r["name"],
            "email": r["email"],
            "role": r["role"],
            "favorite_genre": r["favoritegenre"],
            "loyalty_points": r["loyaltypoints"],
            "created_at": r["createdat"].isoformat() if r["createdat"] else None,
        }
        for r in rows
    ]


# ── Inventory (Showtime Management) ──────────────────────────────────────────

class ShowtimeCreate(BaseModel):
    movie_id: int
    theater_id: int
    date: str        # YYYY-MM-DD
    start_time: str  # HH:MM
    base_price: float


class ShowtimeUpdate(BaseModel):
    base_price: Optional[float] = None


@router.get("/showtimes")
def admin_list_showtimes(current_user: dict = Depends(_admin_check)):
    with get_db() as cur:
        cur.execute(
            """
            SELECT s.ShowtimeID, s.Date, s.StartTime, s.BasePrice, s.CurrentOccupancy,
                   m.Title, m.Genre,
                   t.Name AS TheaterName, t.TotalCapacity, t.ScreenType,
                   df.PredictedOccupancy, df.RecommendationLevel
            FROM Showtimes s
            JOIN Movies m ON s.MovieID = m.MovieID
            JOIN Theaters t ON s.TheaterID = t.TheaterID
            LEFT JOIN Demand_Forecasts df ON df.ShowtimeID = s.ShowtimeID
            WHERE s.Date >= CURRENT_DATE
            ORDER BY s.Date, s.StartTime
            """
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
            "fill_pct": round(r["currentoccupancy"] / r["totalcapacity"] * 100, 1) if r["totalcapacity"] else 0,
            "title": r["title"],
            "genre": r["genre"],
            "theater_name": r["theatername"],
            "screen_type": r["screentype"],
            "predicted_occupancy": float(r["predictedoccupancy"]) if r["predictedoccupancy"] else None,
            "recommendation_level": r["recommendationlevel"],
        }
        for r in rows
    ]


@router.post("/showtimes", status_code=201)
def create_showtime(body: ShowtimeCreate, current_user: dict = Depends(_admin_check)):
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO Showtimes (MovieID, TheaterID, Date, StartTime, BasePrice)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING ShowtimeID
            """,
            (body.movie_id, body.theater_id, body.date, body.start_time, body.base_price),
        )
        row = cur.fetchone()
    return {"showtime_id": row["showtimeid"], "message": "Showtime created"}


@router.put("/showtimes/{showtime_id}")
def update_showtime(showtime_id: int, body: ShowtimeUpdate, current_user: dict = Depends(_admin_check)):
    if body.base_price is None:
        raise HTTPException(status_code=400, detail="Nothing to update")
    with get_db() as cur:
        cur.execute(
            "UPDATE Showtimes SET BasePrice = %s WHERE ShowtimeID = %s RETURNING ShowtimeID",
            (body.base_price, showtime_id),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Showtime not found")
    return {"message": "Showtime updated", "showtime_id": showtime_id}


@router.get("/theaters")
def get_theaters(current_user: dict = Depends(_admin_check)):
    with get_db() as cur:
        cur.execute("SELECT TheaterID, Name, Location, TotalCapacity, ScreenType FROM Theaters ORDER BY Name")
        rows = cur.fetchall()
    return [
        {
            "theater_id": r["theaterid"],
            "name": r["name"],
            "location": r["location"],
            "total_capacity": r["totalcapacity"],
            "screen_type": r["screentype"],
        }
        for r in rows
    ]


@router.get("/stats")
def get_stats(current_user: dict = Depends(_admin_check)):
    """Summary stats for admin dashboard cards."""
    with get_db() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM Users WHERE Role = 'customer'")
        total_customers = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS total FROM Bookings WHERE Status = 'confirmed'")
        total_bookings = cur.fetchone()["total"]

        cur.execute("SELECT COALESCE(SUM(FinalPrice), 0) AS revenue FROM Bookings WHERE Status = 'confirmed'")
        total_revenue = float(cur.fetchone()["revenue"])

        cur.execute(
            """
            SELECT COUNT(*) AS total FROM Showtimes
            WHERE Date >= CURRENT_DATE
            """
        )
        upcoming_shows = cur.fetchone()["total"]

        cur.execute(
            """
            SELECT COUNT(*) AS total FROM Admin_Alerts WHERE Resolved = FALSE
            """
        )
        active_alerts = cur.fetchone()["total"]

    return {
        "total_customers": total_customers,
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "upcoming_shows": upcoming_shows,
        "active_alerts": active_alerts,
    }
