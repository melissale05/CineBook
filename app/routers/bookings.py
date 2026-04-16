"""
Booking routes: create booking, cancel, list user's bookings.
Dynamic pricing is applied at booking time.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List

from app.db.connection import get_db
from app.dependencies import get_current_user
from app.routers.showtimes import _compute_dynamic_price

router = APIRouter()


class BookingRequest(BaseModel):
    showtime_id: int
    seat_numbers: List[str]


@router.post("", status_code=201)
def create_booking(body: BookingRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]

    if not body.seat_numbers:
        raise HTTPException(status_code=400, detail="At least one seat required")

    with get_db() as cur:
        # Load showtime + theater info
        cur.execute(
            """
            SELECT s.ShowtimeID, s.BasePrice, s.CurrentOccupancy,
                   s.Date, s.StartTime, t.TotalCapacity
            FROM Showtimes s
            JOIN Theaters t ON s.TheaterID = t.TheaterID
            WHERE s.ShowtimeID = %s
            """,
            (body.showtime_id,),
        )
        showtime = cur.fetchone()
        if not showtime:
            raise HTTPException(status_code=404, detail="Showtime not found")

        # Check seats not already taken
        cur.execute(
            "SELECT SeatNumber FROM Bookings WHERE ShowtimeID = %s AND Status = 'confirmed'",
            (body.showtime_id,),
        )
        booked = {r["seatnumber"] for r in cur.fetchall()}
        conflicts = [s for s in body.seat_numbers if s in booked]
        if conflicts:
            raise HTTPException(status_code=409, detail=f"Seats already taken: {conflicts}")

        # Capacity check
        available_count = showtime["totalcapacity"] - showtime["currentoccupancy"]
        if len(body.seat_numbers) > available_count:
            raise HTTPException(status_code=409, detail="Not enough available seats")

        # Compute dynamic price
        pricing = _compute_dynamic_price(
            float(showtime["baseprice"]),
            showtime["currentoccupancy"],
            showtime["totalcapacity"],
            showtime["date"],
            showtime["starttime"],
        )
        final_price = pricing["final_price"]

        # Insert bookings
        inserted = []
        for seat in body.seat_numbers:
            cur.execute(
                """
                INSERT INTO Bookings (UserID, ShowtimeID, SeatNumber, FinalPrice, Status)
                VALUES (%s, %s, %s, %s, 'confirmed')
                RETURNING BookingID
                """,
                (user_id, body.showtime_id, seat, final_price),
            )
            bid = cur.fetchone()["bookingid"]
            inserted.append(bid)

        # Award loyalty points (1 per ticket)
        cur.execute(
            "UPDATE Users SET LoyaltyPoints = LoyaltyPoints + %s WHERE UserID = %s",
            (len(body.seat_numbers), user_id),
        )

    return {
        "booking_ids": inserted,
        "seats": body.seat_numbers,
        "final_price_per_seat": final_price,
        "total": round(final_price * len(body.seat_numbers), 2),
        "price_modifier": pricing["price_modifier"],
        "modifier_pct": pricing["modifier_pct"],
        "message": "Booking confirmed",
    }


@router.get("/me")
def my_bookings(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    with get_db() as cur:
        cur.execute(
            """
            SELECT b.BookingID, b.SeatNumber, b.FinalPrice, b.Status, b.BookingTime,
                   s.Date, s.StartTime,
                   m.Title, m.Genre, m.PosterURL,
                   t.Name AS TheaterName, t.ScreenType,
                   s.ShowtimeID
            FROM Bookings b
            JOIN Showtimes s ON b.ShowtimeID = s.ShowtimeID
            JOIN Movies m ON s.MovieID = m.MovieID
            JOIN Theaters t ON s.TheaterID = t.TheaterID
            WHERE b.UserID = %s
            ORDER BY s.Date DESC, s.StartTime DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()

    return [
        {
            "booking_id": r["bookingid"],
            "seat_number": r["seatnumber"],
            "final_price": float(r["finalprice"]),
            "status": r["status"],
            "booking_time": r["bookingtime"].isoformat() if r["bookingtime"] else None,
            "showtime_id": r["showtimeid"],
            "date": str(r["date"]),
            "start_time": str(r["starttime"]),
            "title": r["title"],
            "genre": r["genre"],
            "poster_url": r["posterurl"],
            "theater_name": r["theatername"],
            "screen_type": r["screentype"],
        }
        for r in rows
    ]


@router.delete("/{booking_id}")
def cancel_booking(booking_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    with get_db() as cur:
        cur.execute(
            "SELECT BookingID, UserID, Status FROM Bookings WHERE BookingID = %s",
            (booking_id,),
        )
        booking = cur.fetchone()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        if booking["userid"] != user_id:
            raise HTTPException(status_code=403, detail="Not your booking")
        if booking["status"] == "cancelled":
            raise HTTPException(status_code=400, detail="Already cancelled")

        cur.execute(
            "UPDATE Bookings SET Status = 'cancelled' WHERE BookingID = %s",
            (booking_id,),
        )
        # Remove loyalty point
        cur.execute(
            "UPDATE Users SET LoyaltyPoints = GREATEST(LoyaltyPoints - 1, 0) WHERE UserID = %s",
            (user_id,),
        )

    return {"message": "Booking cancelled", "booking_id": booking_id}
