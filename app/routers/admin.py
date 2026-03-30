from fastapi import APIRouter, HTTPException
from app.db.connection import get_db

router = APIRouter()


def check_admin(user_id):
    with get_db() as cur:
        cur.execute("SELECT Role FROM Users WHERE UserID = %s", (user_id,))
        user = cur.fetchone()
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/showtimes")
def admin_showtimes(user_id: int):
    check_admin(user_id)

    with get_db() as cur:
        cur.execute("SELECT * FROM Showtimes")
        return cur.fetchall()


@router.get("/bookings")
def admin_bookings(user_id: int):
    check_admin(user_id)

    with get_db() as cur:
        cur.execute("SELECT * FROM Bookings")
        return cur.fetchall()


@router.get("/revenue")
def admin_revenue(user_id: int):
    check_admin(user_id)

    with get_db() as cur:
        cur.execute("""
            SELECT SUM(FinalPrice) as total_revenue
            FROM Bookings
            WHERE Status = 'confirmed'
        """)
        return cur.fetchone()
