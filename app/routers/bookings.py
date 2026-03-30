from fastapi import APIRouter, HTTPException
from app.db.connection import get_db

router = APIRouter()


@router.post("/")
def create_booking(user_id: int, showtime_id: int, seat: str, price: float):
    with get_db() as cur:
        try:
            cur.execute("""
                INSERT INTO Bookings (UserID, ShowtimeID, SeatNumber, FinalPrice)
                VALUES (%s, %s, %s, %s)
                RETURNING BookingID
            """, (user_id, showtime_id, seat, price))

            return {"message": "Booking created"}
        except Exception:
            raise HTTPException(status_code=400, detail="Seat already taken")


@router.get("/me/{user_id}")
def get_user_bookings(user_id: int):
    with get_db() as cur:
        cur.execute("""
            SELECT * FROM Bookings WHERE UserID = %s
        """, (user_id,))
        return cur.fetchall()


@router.delete("/{booking_id}")
def delete_booking(booking_id: int):
    with get_db() as cur:
        cur.execute("DELETE FROM Bookings WHERE BookingID = %s", (booking_id,))
        return {"message": "Booking deleted"}
